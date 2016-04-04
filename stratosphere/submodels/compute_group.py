from annoying.fields import JSONField

from datetime import datetime, timedelta

from django.apps import apps
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import connection, models, transaction, OperationalError
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..models import ComputeInstance, ProviderConfiguration, ProviderSize
from ..util import HasLogger, retry, call_with_retry, thread_local

import json

import traceback


class InstanceStatesSnapshot(models.Model):
    class Meta:
        app_label = "stratosphere"

    user_configuration = models.ForeignKey('UserConfiguration', related_name='instance_states_snapshots')
    time = models.DateTimeField()

    pending    = models.IntegerField()
    running    = models.IntegerField()
    terminated = models.IntegerField()


class GroupInstanceStatesSnapshot(models.Model):
    class Meta:
        app_label = "stratosphere"

    user_snapshot = models.ForeignKey('InstanceStatesSnapshot', related_name='group_snapshots')
    group = models.ForeignKey('ComputeGroup', related_name='instance_states_snapshots')

    pending    = models.IntegerField()
    running    = models.IntegerField()
    terminated = models.IntegerField()


class ComputeGroupBase(models.Model, HasLogger, SaveTheChange, TrackChanges):
    class Meta:
        abstract = True

    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    TERMINATED = 'TERMINATED'

    STATE_CHOICES = (
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (TERMINATED, 'Terminated'),
    )

    user_configuration = models.ForeignKey('UserConfiguration', related_name='compute_groups')
    image = models.ForeignKey('OperatingSystemImage', related_name='compute_groups')
    instance_count = models.IntegerField()
    cpu = models.IntegerField()
    memory = models.IntegerField()
    name = models.CharField(max_length=128)
    provider_policy = JSONField()
    size_distribution = JSONField()
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    authentication_method = models.ForeignKey('AuthenticationMethod', related_name='compute_groups')

    @classmethod
    def quick_create(cls, instance_count=5):
        from ..models import UserConfiguration, OperatingSystemImage, AuthenticationMethod, Provider
        image = OperatingSystemImage.objects.first()
        providers = Provider.objects.filter(disk_image_mappings__operating_system_image=image)
        provider_policy = {p.name: 'auto' for p in providers}
        return cls.objects.create(user_configuration=UserConfiguration.objects.first(),
                                  image=image, cpu=1, memory=512,
                                  instance_count=instance_count, name='sdfsdf', provider_policy=provider_policy,
                                  size_distribution={}, authentication_method=AuthenticationMethod.objects.first())

    def provider_states(self):
        provider_states_map = {}
        now = timezone.now()

        for provider_name in self.provider_policy:
            provider_configuration = ProviderConfiguration.objects.get(provider_name=provider_name, user_configuration=self.user_configuration)
            provider_instances = self.instances.filter(provider_image__provider__name=provider_name, terminated=False)

            running_count = len(list(filter(lambda i: i.is_running(now), provider_instances)))
            pending_count = len(list(filter(lambda i: i.is_pending(now), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.is_terminated(now), provider_instances)))

            icon_path = staticfiles_storage.url(provider_configuration.provider.icon_path)

            provider_states_map[provider_name] = {
                'id': provider_configuration.pk,
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.provider.pretty_name,
                'icon_path': icon_path,
            }

        return provider_states_map

    @thread_local(DB_OVERRIDE='serializable')
    def check_instance_distribution(self):
        with transaction.atomic():
            now = timezone.now()

            if self.state == self.TERMINATED:
                non_terminated_count = self.instances.filter(~ComputeInstance.terminated_instances_query(now)).count()
                self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
                if non_terminated_count == 0:
                    self.logger.warn('Deleting self')
                    self.delete()

            else:
                self.logger.info('Group state is %s; ensuring running instance count no less than expected' % self.state)

                running_count = self.instances.filter(ComputeInstance.running_instances_query(now)).count()
                self.logger.info('running_count < self.instance_count = %d < %d' % (running_count, self.instance_count))

                if running_count >= self.instance_count and self.state == self.PENDING:
                    self.state = self.RUNNING
                    self.save()

                provider_configurations = self.user_configuration.provider_configurations
                good_provider_ids = [provider.pk for provider in provider_configurations.filter(enabled=True)]

                self.logger.warn('good providers: %s' % good_provider_ids)

            if running_count != self.instance_count:
                self.logger.warn('Rebalancing instances')
                self.rebalance_instances(good_provider_ids)

    @thread_local(DB_OVERRIDE='serializable')
    def rebalance_instances(self, provider_ids=None):
        best_sizes = self._get_best_sizes(provider_ids)

        # if there aren't any providers left deploy the required number of
        # instances to every provider in hopes that one of them will work
        if len(best_sizes) == 0:
            self.logger.warn('No sizes available for any provider; rebalancing across all providers as a Hail Mary')
            best_sizes = self._get_best_sizes()
            instance_counts_by_size_id = self._get_emergency_size_distribution(best_sizes)
        else:
            instance_counts_by_size_id = self._get_size_distribution(best_sizes)

        self.logger.info('New size distribution: %s' % instance_counts_by_size_id)
        self.size_distribution = instance_counts_by_size_id
        self.save()

        self._create_compute_instances()

        self.user_configuration.take_instance_states_snapshot_if_changed()

    @thread_local(DB_OVERRIDE='serializable')
    def terminate_instance(self, instance):
        with transaction.atomic():
            self.instance_count -= 1
            self.save()

            instance.terminate()

    @retry(OperationalError)
    @thread_local(DB_OVERRIDE='serializable')
    def terminate(self):
        with transaction.atomic():
            self.state = self.TERMINATED
            self.instance_count = 0
            self.save()

    def create_phantom_instance_states_snapshot(self, now):
        # TODO figure out how to make this more consistent without causing a bunch of transaction conflicts
        instances = list(self.instances.all())

        args = {
            'group': self,
            'pending': len(list(filter(lambda i: i.is_pending(now), instances))),
            'running': len(list(filter(lambda i: i.is_running(now), instances))),
            'terminated': len(list(filter(lambda i: i.is_terminated(now), instances))),
        }

        return GroupInstanceStatesSnapshot(**args)

    def _get_best_sizes(self, allowed_provider_ids=None):
        best_sizes = {}
        for provider_name in self.provider_policy:
            self.logger.debug('Getting sizes for provider %s and image %s' % (provider_name, self.image))
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                available_sizes = []

                provider_image = provider_configuration.available_provider_images.filter(disk_image__disk_image_mappings__operating_system_image=self.image).first()
                if provider_image is None:
                    self.logger.debug('No provider image available')
                else:
                    provider_sizes = provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory)
                    self.logger.debug('Provider sizes for image %s, cpu %d, memory %d: %s' % (provider_image, self.cpu, self.memory, provider_sizes))
                    available_sizes.extend(provider_sizes)

                available_sizes.sort(key=lambda s: s.price)
                if len(available_sizes) > 0:
                    best_size = available_sizes[0]
                    self.logger.debug('Best size: %s' % best_size)
                    best_sizes[provider_name] = best_size
                else:
                    self.logger.debug('No sizes available')
            else:
                self.logger.debug('Provider %s not allowed' % provider_name)

        return best_sizes

    @staticmethod
    def _sorted_sizes(sizes):
        # sort to ensure consistency across multiple runs, e.g. when a size has the
        # same price in multiple AWS regions
        return sorted(sizes.values(), key=lambda s: s.pk) # sort on secondary key

    @staticmethod
    def _get_provider_size_key(provider_size):
        # the database converts to string keys anyway, so we do it here for consistency
        return str(provider_size.pk)

    def _get_size_distribution(self, sizes):
        instance_counts = {self._get_provider_size_key(provider_size): 0 for provider_size in sizes.values()}

        # if len(sizes) == 0, the following gets into an infinite loop
        if len(sizes) > 0:
            sizes_list = self._sorted_sizes(sizes)

            while sum(instance_counts.values()) < self.instance_count:
                remaining_instance_count = self.instance_count - sum(instance_counts.values())
                provider_instance_count = int(remaining_instance_count/len(sizes))

                for provider_size in sizes_list:
                    # correct for rounding down when dividing remaining instances by number of sizes
                    if provider_instance_count == 0 and sum(instance_counts.values()) < self.instance_count:
                        corrected_provider_instance_count = 1
                    else:
                        corrected_provider_instance_count = provider_instance_count

                    key = self._get_provider_size_key(provider_size)
                    instance_counts[key] += corrected_provider_instance_count

        return instance_counts

    def _get_emergency_size_distribution(self, sizes):
        sizes_list = self._sorted_sizes(sizes)
        instance_counts = {}

        for provider_size in sizes_list:
            key = self._get_provider_size_key(provider_size)

            # cap the number of instances that can be created in Hail Mary mode
            if provider_size.provider_configuration.failure_count < self.instance_count * 3:
                instance_counts[key] = self.instance_count
            else:
                self.logger.warn('Not creating more instances in Hail Mary mode for provider %d' %
                                 provider_size.provider_configuration.pk)

        return instance_counts

    def _pending_or_running_count(self, provider_size):
        now = timezone.now()
        query = Q(state__in=(ComputeInstance.PENDING, ComputeInstance.RUNNING)) | Q(state=None)
        query &= Q(provider_size=provider_size)
        instances = self.instances.filter(query)
        return len([i.is_pending(now) or i.is_running(now) for i in instances])

    def _create_compute_instances(self):
        with transaction.atomic():
            self.logger.info('Size distribution: %s' % self.size_distribution)
            terminate_instances = []

            for provider_size_id, size_instance_count in self.size_distribution.items():
                provider_size = ProviderSize.objects.get(pk=provider_size_id)
                provider_configuration = provider_size.provider_configuration

                self.logger.info('Balancing compute instances for size %s; expected count %d' %
                                 (provider_size, size_instance_count))

                pending_or_running_count = self._pending_or_running_count(provider_size)

                running_provider_instances = self.instances.filter(provider_size=provider_size,
                                                                   state=ComputeInstance.RUNNING)
                running_count = running_provider_instances.count()

                self.logger.info('pending_or_running_count: %d, running_count: %d' %
                                 (pending_or_running_count, running_count))

                # filter on provider as well, since available_provider_images could contain shared images
                # TODO wait, does that make sense?
                # TODO could this also produce multiple images if we don't specify the provider size?
                provider_image = provider_configuration.available_provider_images.get(
                                        disk_image__disk_image_mappings__operating_system_image=self.image,
                                        disk_image__disk_image_mappings__provider=provider_configuration.provider)

                if pending_or_running_count < size_instance_count:
                    instances_to_create = size_instance_count - pending_or_running_count
                    self.logger.warn('Creating %d instances' % instances_to_create)

                    for i in range(instances_to_create):
                        instance_name = '%s-%d' % (self.name, i)

                        compute_instance_args = {
                            'name': instance_name,
                            'provider_image': provider_image,
                            'group': self,
                            'provider_size': provider_size,
                            'extra': {},
                            'provider_configuration': provider_configuration,
                            'state': None,
                            'public_ips': [],
                            'private_ips': [],
                        }

                        compute_instance = ComputeInstance.objects.create(**compute_instance_args)
                        self.logger.info('Created instance %d for provider_size %s' % (compute_instance.pk, provider_size))

                elif running_count > size_instance_count:
                    extra_instances = list(running_provider_instances)[:running_count - size_instance_count]
                    self.logger.info('Found %d extra instances for size %s' % (len(extra_instances), provider_size))
                    terminate_instances.extend(extra_instances)

            # TODO make sure this squares with multi-row transaction isolation
            missing_size_instances = self.instances.filter(~Q(provider_size__pk__in=self.size_distribution.keys()))
            terminate_instances.extend(missing_size_instances)

            self.logger.info('Found %d instances for sizes not in size distribution' % len(missing_size_instances))

            if len(terminate_instances) > 0:
                total_running_count = self.instances.filter(state=ComputeInstance.RUNNING).count()
                if total_running_count < self.instance_count:
                    # Two motivations here: we stop ourselves from getting unlucky by accidentally terminating an
                    # instance that's just having a bad minute, and we also stop ourselves from terminating instances
                    # that are taking so long to start up that they're considered as failed. The latter can get into
                    # a loop of continually starting, timing out, and restarting instances, otherwise.
                    self.logger.warn('Not terminating extraneous instances while running count is less than or equal to expected count')
                else:
                    for instance in terminate_instances:
                        self.logger.warn('Terminating instance %s for size %s' % (instance, instance.provider_size))
                        instance.terminate()