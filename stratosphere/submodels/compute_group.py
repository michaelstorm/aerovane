from annoying.fields import JSONField

from datetime import datetime, timedelta

from django.apps import apps
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import connection, models, transaction, OperationalError
from django.db.models import Q
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
    updating_distribution = models.BooleanField(default=False)
    updating_distribution_time = models.DateTimeField(blank=True, null=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    authentication_method = models.ForeignKey('AuthenticationMethod', related_name='compute_groups')

    def provider_states(self):
        provider_states_map = {}

        for provider_name in self.provider_policy:
            provider_configuration = ProviderConfiguration.objects.get(provider_name=provider_name)
            provider_instances = self.instances.filter(provider_image__provider__name=provider_name)
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (None, ComputeInstance.PENDING, ComputeInstance.REBOOTING), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING) and not i.terminated,
                                               provider_instances)))

            provider_states_map[provider_name] = {
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.provider.pretty_name,
                'icon_path': provider_configuration.provider.icon_path,
            }

        return provider_states_map

    @thread_local(DB_OVERRIDE='serializable')
    def check_instance_distribution(self):
        with transaction.atomic():
            self.logger.warning('Got lock on compute group %d' % self.pk)

            self.logger.warning('%s state: %s' % (self.name, self.state))

            instances_flat = list(self.instances.all())
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
            non_pending_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.PENDING), instances_flat)))
            non_terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.TERMINATED, ComputeInstance.UNKNOWN), instances_flat)))

            good_provider_ids = [provider.pk for provider in self.user_configuration.provider_configurations.all()]

            if self.state == self.TERMINATED:
                self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
                if non_terminated_count == 0:
                    self.logger.warn('Deleting self')
                    self.delete()

            else:
                if self.state == self.PENDING and non_pending_count >= self.instance_count:
                    self.state = self.RUNNING
                    self.save()

                if self.state == self.RUNNING:
                    self.logger.warn('running_count < self.instance_count = %d < %d = %s' %
                                     (running_count, self.instance_count, running_count < self.instance_count))

                    if running_count < self.instance_count:
                        # state__in=[None] returns empty list no matter what
                        bad_instances = self.instances.exclude(state__in=(ComputeInstance.PENDING, ComputeInstance.RUNNING)).exclude(state=None)
                        self.logger.warning('bad instances: %s' % [i.pk for i in bad_instances])

                        bad_provider_ids = set([instance.provider_configuration.pk for instance in bad_instances])
                        good_provider_ids = [provider.pk for provider in
                                             self.user_configuration.provider_configurations.exclude(pk__in=bad_provider_ids)]

                        self.logger.warning('bad_provider_ids: %s' % bad_provider_ids)
                        self.logger.warning('good_provider_ids: %s' % good_provider_ids)

            if running_count != self.instance_count:
                self.rebalance_instances(good_provider_ids)

    @thread_local(DB_OVERRIDE='serializable')
    def rebalance_instances(self, provider_ids=None):
        best_sizes = self._get_best_sizes(provider_ids)

        # if there aren't any providers left, then fuck it; deploy the required number of
        # instances to every provider in hopes that one of them will work
        if len(best_sizes) == 0:
            best_sizes = self._get_best_sizes()
            instance_counts_by_size_id = self._get_emergency_size_distribution(best_sizes)
        else:
            instance_counts_by_size_id = self._get_size_distribution(best_sizes)

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
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                available_sizes = []

                provider_image = provider_configuration.available_provider_images.filter(disk_image__disk_image_mappings__operating_system_image=self.image).first()
                if provider_image is not None:
                    provider_sizes = provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory)
                    available_sizes.extend(provider_sizes)

                available_sizes.sort(key=lambda s: s.price)
                if len(available_sizes) > 0:
                    best_sizes[provider_name] = available_sizes[0]

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
        self.logger.warning('sizes_list: %s' % sizes_list)

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
            self.logger.warning('size_distribution: %s' % self.size_distribution)
            terminate_instances = []

            for provider_size_id, instance_count in self.size_distribution.items():
                provider_size = ProviderSize.objects.get(pk=provider_size_id)
                provider_configuration = provider_size.provider_configuration

                pending_or_running_count = self._pending_or_running_count(provider_size)

                running_provider_instances = self.instances.filter(provider_size=provider_size,
                                                                   state=ComputeInstance.RUNNING)
                running_count = running_provider_instances.count()

                print('pending_or_running_count: %d, running_count: %d' % (pending_or_running_count, running_count))

                # filter on provider as well, since available_provider_images could contain shared images
                # TODO wait, does that make sense?
                # TODO could this also produce multiple images if we don't specify the provider size?
                provider_image = provider_configuration.available_provider_images.get(
                                        disk_image__disk_image_mappings__operating_system_image=self.image,
                                        disk_image__disk_image_mappings__provider=provider_configuration.provider)

                if pending_or_running_count < instance_count:
                    for i in range(instance_count - pending_or_running_count):
                        self.logger.warning('creating instance for size %s' % provider_size)
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

                        with transaction.atomic():
                            intended_instance_count = self.size_distribution[str(provider_size.pk)]
                            current_instance_count = self._pending_or_running_count(provider_size)

                            print('size_distribution: %s' % self.size_distribution)
                            print('%s: current_instance_count < intended_instance_count = %d < %d = %s' %
                                  (provider_size, current_instance_count, intended_instance_count,
                                   current_instance_count < intended_instance_count))

                            if current_instance_count < intended_instance_count:
                                compute_instance = ComputeInstance.objects.create(**compute_instance_args)
                                print('created instance %d for provider_size %s' % (compute_instance.pk, provider_size))

                                # lexical scoping in loop
                                connection.on_commit(lambda c=compute_instance: c.schedule_create_libcloud_node_job())

                elif running_count > instance_count:
                    terminate_instances.extend(list(running_provider_instances)[:running_count - instance_count])

            # TODO make sure this squares with multi-row transaction isolation
            missing_size_instances = self.instances.filter(~Q(provider_size__pk__in=self.size_distribution.keys()))
            terminate_instances.extend(missing_size_instances)

            for instance in terminate_instances:
                self.logger.warning('terminating instance %s for size %s' % (instance, instance.provider_size))
                instance.terminate()