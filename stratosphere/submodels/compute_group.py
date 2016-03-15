from annoying.fields import JSONField

from datetime import datetime, timedelta

from django.apps import apps
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import connection, models, transaction, OperationalError
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from save_the_change.mixins import SaveTheChange

from ..models import ComputeInstance, ProviderConfiguration, ProviderSize
from ..util import HasLogger, retry, call_with_retry, thread_local

import json

import traceback


class InstanceStatesSnapshot(models.Model):
    class Meta:
        app_label = "stratosphere"

    user_configuration = models.ForeignKey('UserConfiguration', related_name='instance_states_snapshots')
    time = models.DateTimeField()

    running    = models.IntegerField()
    rebooting  = models.IntegerField()
    terminated = models.IntegerField()
    pending    = models.IntegerField()
    stopped    = models.IntegerField()
    suspended  = models.IntegerField()
    paused     = models.IntegerField()
    error      = models.IntegerField()
    unknown    = models.IntegerField()


class GroupInstanceStatesSnapshot(models.Model):
    class Meta:
        app_label = "stratosphere"

    user_snapshot = models.ForeignKey('InstanceStatesSnapshot', related_name='group_snapshots')
    group = models.ForeignKey('ComputeGroup', related_name='instance_states_snapshots')

    running    = models.IntegerField()
    rebooting  = models.IntegerField()
    terminated = models.IntegerField()
    pending    = models.IntegerField()
    stopped    = models.IntegerField()
    suspended  = models.IntegerField()
    paused     = models.IntegerField()
    error      = models.IntegerField()
    unknown    = models.IntegerField()


class ComputeGroupBase(models.Model, HasLogger, SaveTheChange):
    class Meta:
        abstract = True

    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    TERMINATED = 'TERMINATED'

    STATE_CHOICES = (
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (STOPPED, 'Stopped'),
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
    last_state_update_time = models.DateTimeField()

    def provider_states(self):
        provider_states_map = {}
        now = timezone.now()
        two_minutes_ago = now - timedelta(minutes=2)
        four_minutes_ago = now - timedelta(minutes=4)

        def instance_terminated(i):
            pending_or_running_states = None, ComputeInstance.RUNNING, ComputeInstance.PENDING
            not_pending_or_running = i.state not in pending_or_running_states
            pending_or_running_and_expired = i.state in pending_or_running_states and i.last_request_start_time < two_minutes_ago
            unknown_and_not_expired = i.state not in pending_or_running_states and i.last_state_update_time >= four_minutes_ago
            return not_pending_or_running or pending_or_running_and_expired or unknown_and_not_expired

        for provider_name in self.provider_policy:
            provider_configuration = ProviderConfiguration.objects.get(provider_name=provider_name, user_configuration=self.user_configuration)
            provider_instances = self.instances.filter(provider_image__provider__name=provider_name, terminated=False)

            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (None, ComputeInstance.PENDING) and i.last_request_start_time >= two_minutes_ago, provider_instances)))

            if running_count >= self.instance_count:
                terminated_count = 0
            else:
                terminated_count = len(list(filter(instance_terminated, provider_instances)))

            icon_path = staticfiles_storage.url(provider_configuration.provider.icon_path)

            provider_states_map[provider_name] = {
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
            instances_flat = list(self.instances.all())

            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
            non_pending_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.PENDING), instances_flat)))
            non_terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.TERMINATED, ComputeInstance.UNKNOWN), instances_flat)))

            if self.state == self.TERMINATED:
                self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
                if non_terminated_count == 0:
                    self.logger.warn('Deleting self')
                    self.delete()

            elif self.state == self.PENDING and non_pending_count >= self.instance_count:
                self.logger.info('State is currently pending and non-pending count >= instance_count (%d >= %d); ' + \
                                 'setting group state to RUNNING' % (non_pending_count, self.instance_count))
                self.state = self.RUNNING
                self.save()

            elif self.state == self.RUNNING:
                self.logger.info('Group state is RUNNING; ensuring running instance count no less than expected')
                self.logger.info('running_count < self.instance_count = %d < %d' % (running_count, self.instance_count))

                if running_count < self.instance_count:
                    self.logger.warn('Running count is less than expected count')

                    # state__in=[None] returns empty list no matter what
                    bad_instances = self.instances.exclude(state__in=(ComputeInstance.PENDING, ComputeInstance.RUNNING)).exclude(state=None)
                    self.logger.warn('bad instances: %s' % [i.pk for i in bad_instances])

                    bad_provider_ids = set([instance.provider_configuration.pk for instance in bad_instances])
                    good_provider_ids = [provider.pk for provider in
                                         self.user_configuration.provider_configurations.exclude(pk__in=bad_provider_ids)]

                    self.logger.warn('bad providers: %s' % bad_provider_ids)
                    self.logger.warn('good providers: %s' % good_provider_ids)

                else:
                    good_provider_ids = self.user_configuration.provider_configurations.values_list('id', flat=True)

                if running_count != self.instance_count:
                    self.logger.warn('Rebalancing instances')
                    self.rebalance_instances(good_provider_ids)

    @thread_local(DB_OVERRIDE='serializable')
    def rebalance_instances(self, provider_ids=None):
        best_sizes = self._get_best_sizes(provider_ids)

        # if there aren't any providers left, then fuck it; deploy the required number of
        # instances to every provider in hopes that one of them will work
        if len(best_sizes) == 0:
            self.logger.warn('No sizes available for any provider; rebalancing across all providers as a Hail Mary')
            best_sizes = self._get_best_sizes()
            instance_counts_by_size_id = self._get_emergency_size_distribution(best_sizes)
        else:
            instance_counts_by_size_id = self._get_size_distribution(best_sizes)

        self.logger.warn('New size distribution: %s' % instance_counts_by_size_id)
        self.size_distribution = instance_counts_by_size_id
        self.save()

        self._create_compute_instances()

    @thread_local(DB_OVERRIDE='serializable')
    def terminate_instance(self, instance):
        with transaction.atomic():
            self.instance_count -= 1
            self.save()

            instance.terminate()

    @retry(OperationalError)
    def terminate(self):
        with transaction.atomic():
            self.state = self.TERMINATED
            self.instance_count = 0
            self.save()

    def create_phantom_instance_states_snapshot(self, now):
        # TODO figure out how to make this more consistent without causing a bunch of transaction conflicts
        instances = list(self.instances.all())

        two_minutes_ago = now - timedelta(minutes=2)
        def filter_instance_states(two_minutes_ago, states):
            return lambda i: i.state in states and (not i.terminated or i.last_request_start_time < two_minutes_ago)

        args = {
            'group': self,
            'running': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.RUNNING]), instances))),
            'rebooting': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.REBOOTING]), instances))),
            'terminated': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.TERMINATED]), instances))),
            'pending': len(list(filter(filter_instance_states(two_minutes_ago, [None, ComputeInstance.PENDING]), instances))),
            'stopped': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.STOPPED]), instances))),
            'suspended': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.SUSPENDED]), instances))),
            'paused': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.PAUSED]), instances))),
            'error': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.ERROR]), instances))),
            'unknown': len(list(filter(filter_instance_states(two_minutes_ago, [ComputeInstance.UNKNOWN]), instances))),
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
        sizes_list = self._sorted_sizes(sizes)

        instance_counts = {}

        # if len(sizes) == 0, the following gets into an infinite loop
        if len(sizes) > 0:
            while sum(instance_counts.values()) < self.instance_count:
                remaining_instance_count = self.instance_count - sum(instance_counts.values())
                provider_instance_count = int(remaining_instance_count/len(sizes))

                for provider_size in sizes_list:
                    if provider_instance_count == 0 and sum(instance_counts.values()) < self.instance_count:
                        adjusted_provider_instance_count = 1
                    else:
                        adjusted_provider_instance_count = provider_instance_count

                    key = self._get_provider_size_key(provider_size)
                    if key in instance_counts:
                        instance_counts[key] += adjusted_provider_instance_count
                    else:
                        instance_counts[key] = adjusted_provider_instance_count

        return instance_counts

    def _get_emergency_size_distribution(self, sizes):
        sizes_list = self._sorted_sizes(sizes)
        self.logger.warning('sizes_list: %s' % sizes_list)

        instance_counts = {}

        for provider_size in sizes_list:
            key = self._get_provider_size_key(provider_size)
            instance_counts[key] = self.instance_count

        return instance_counts

    def _pending_or_running_count(self, provider_size):
        now = timezone.now()
        return self.instances.filter(
            Q(provider_size=provider_size)
            & (Q(state=ComputeInstance.RUNNING)
               | Q(state=None,
                   last_request_start_time__gt=now - timedelta(minutes=2))
               | Q(state=ComputeInstance.PENDING,
                   last_request_start_time__gt=now - timedelta(minutes=5))
        )).count()

    def _create_compute_instances(self):
        with transaction.atomic():
            self.logger.info('Size distribution: %s' % self.size_distribution)
            terminate_instances = []

            for provider_size_id, size_instance_count in self.size_distribution.items():
                provider_size = ProviderSize.objects.get(pk=provider_size_id)
                provider_configuration = provider_size.provider_configuration

                pending_or_running_count = self._pending_or_running_count(provider_size)

                running_provider_instances = self.instances.filter(provider_size=provider_size,
                                                                   state=ComputeInstance.RUNNING)
                running_count = running_provider_instances.count()

                self.logger.info('pending_or_running_count: %d, running_count: %d' % (pending_or_running_count, running_count))

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
                            'last_request_start_time': timezone.now(),
                        }

                        compute_instance = ComputeInstance.objects.create(**compute_instance_args)
                        print('created instance %d for provider_size %s' % (compute_instance.pk, provider_size))

                        # lexical scoping in loop
                        connection.on_commit(lambda c=compute_instance: c.schedule_create_libcloud_node_job())

                elif running_count > size_instance_count:
                    terminate_instances.extend(list(running_provider_instances)[:running_count - size_instance_count])

            # TODO make sure this squares with multi-row transaction isolation
            missing_size_instances = self.instances.filter(~Q(provider_size__pk__in=self.size_distribution.keys()))
            terminate_instances.extend(missing_size_instances)

            for instance in terminate_instances:
                self.logger.warning('terminating instance %s for size %s' % (instance, instance.provider_size))
                instance.terminate()