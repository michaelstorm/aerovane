from annoying.fields import JSONField

from datetime import datetime, timedelta

from django.db import models, transaction, OperationalError
from django.db.models import Q

from polymorphic import PolymorphicModel

from ..models import ComputeInstance, ProviderConfiguration, ProviderSize
from ..util import HasLogger, retry, call_with_retry, BackoffError

import json

import traceback


class NoSizesAvailableError(Exception):
    pass


def update_distribution(func):
    def func_wrapper(self):
        def lock():
            print('ATTEMPTING LOCK')
            with transaction.atomic():
                cutoff_time = datetime.now() + timedelta(minutes=2)
                if self.updating_distribution and self.updating_distribution_time < cutoff_time:
                    raise BackoffError()
                else:
                    print('LOCKING')
                    self.updating_distribution = True
                    self.updating_distribution_time = datetime.now()
                    self.save()

        def unlock():
            print('ATTEMPTING UNLOCK')
            saved = False
            while not saved:
                try:
                    with transaction.atomic():
                        # don't re-save if deleted earlier
                        if ComputeGroup.objects.filter(pk=self.pk).exists():
                            print('UNLOCKING')
                            self.updating_distribution = False
                            self.save()

                        saved = True

                except OperationalError:
                    pass

        try:
            lock()
            func(self)
        finally:
            call_with_retry(unlock, OperationalError, tries=10)

    return func_wrapper


class ComputeGroup(PolymorphicModel, HasLogger):
    class Meta:
        app_label = "stratosphere"

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
            terminated_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING),
                                               provider_instances)))

            provider_states_map[provider_name] = {
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.provider.pretty_name,
                'icon_path': provider_configuration.provider.icon_path,
            }

        return provider_states_map

    @update_distribution
    def check_instance_distribution(self):
        self.logger.warning('Got lock')

        self.logger.warning('%s state: %s' % (self.name, self.state))

        instances_flat = list(self.instances.all())
        running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
        non_pending_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.PENDING), instances_flat)))
        non_terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.TERMINATED, ComputeInstance.UNKNOWN), instances_flat)))
        non_running_instances = list(filter(lambda i: i.state != ComputeInstance.RUNNING, instances_flat))

        if self.state == self.TERMINATED:
            self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
            if non_terminated_count == 0:
                self.logger.info('Deleting self.')
                self.delete()
        else:
            if self.state == self.PENDING and non_pending_count >= self.instance_count:
                self.state = self.RUNNING

            self.logger.warn('running_count < self.instance_count = %d < %d = %s' %
                             (running_count, self.instance_count, running_count < self.instance_count))

            if running_count < self.instance_count:
                bad_provider_ids = set([instance.provider_configuration.pk for instance in self.instances.filter(~Q(state__in=[None, ComputeInstance.PENDING, ComputeInstance.RUNNING]))])
                good_provider_ids = [provider.pk for provider in
                                     self.user_configuration.provider_configurations.exclude(pk__in=bad_provider_ids)]

                self.logger.warning('bad_provider_ids: %s' % bad_provider_ids)
                self.logger.warning('good_provider_ids: %s' % good_provider_ids)

                self.create_instances(good_provider_ids)

            if running_count >= self.instance_count:
                for instance in non_running_instances:
                    self._destroy_instance(instance) # TODO currently no-op

    def _destroy_instance(self, instance):
        pass

    def create_instances(self, provider_ids=None):
        best_sizes = self._get_best_sizes(provider_ids)

        instance_counts_by_size_id = self._get_size_distribution(best_sizes)
        self.size_distribution = instance_counts_by_size_id
        self.save()

        self._create_compute_instances()

    @retry(OperationalError)
    def terminate(self):
        self.state = self.TERMINATED
        self.save()

        for instance in self.instances.all():
            try:
                instance.provider_configuration.driver.destroy_node(instance.to_libcloud_node())
            except Exception:
                traceback.print_exc()


class ImageComputeGroup(ComputeGroup):
    class Meta:
        app_label = "stratosphere"

    image = models.ForeignKey('DiskImage', related_name='compute_groups')


class OperatingSystemComputeGroup(ComputeGroup):
    class Meta:
        app_label = "stratosphere"

    image = models.ForeignKey('OperatingSystemImage', related_name='compute_groups')

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

    def _get_size_distribution(self, sizes):
        # sort to ensure consistency across multiple runs, e.g. when a size has the
        # same price in multiple AWS regions
        sizes_list = sorted(sizes.values(), key=lambda s: s.pk) # sort on secondary key
        self.logger.warning('sizes_list: %s' % sizes_list)

        instance_counts = {}
        remaining_instance_count = self.instance_count

        if len(sizes) > 0:
            while remaining_instance_count > 0:
                for provider_size in sizes_list:
                    provider_instance_count = int(remaining_instance_count/len(sizes)) * len(sizes)
                    if provider_instance_count == 0 and remaining_instance_count > 0:
                        provider_instance_count = 1

                    # the database converts to string keys anyway, so we do it here for consistency
                    if provider_size.pk in instance_counts:
                        instance_counts[str(provider_size.pk)] += provider_instance_count
                    else:
                        instance_counts[str(provider_size.pk)] = provider_instance_count

                    remaining_instance_count -= provider_instance_count

        return instance_counts

    def pending_or_running_count(self, provider_size):
        return self.instances.filter(
            Q(provider_size=provider_size)
            & (Q(state=ComputeInstance.RUNNING)
               | Q(state=None,
                   last_request_start_time__gt=datetime.now() - timedelta(minutes=2))
               | Q(state=ComputeInstance.PENDING,
                   last_request_start_time__gt=datetime.now() - timedelta(minutes=5))
        )).count()

    def _create_compute_instances(self):
        with transaction.atomic():
            self.logger.warning('size_distribution: %s' % self.size_distribution)
            for provider_size_id, instance_count in self.size_distribution.items():
                provider_size = ProviderSize.objects.get(pk=provider_size_id)
                provider_configuration = provider_size.provider_configuration

                running_count = self.pending_or_running_count(provider_size)

                actually_running_count = self.instances.filter(provider_size=provider_size, state=ComputeInstance.RUNNING).count()
                created_count = self.instances.filter(provider_size=provider_size, state=None, last_request_start_time__gt=datetime.now() - timedelta(minutes=2)).count()
                pending_count = self.instances.filter(provider_size=provider_size, state=ComputeInstance.PENDING, last_request_start_time__gt=datetime.now() - timedelta(minutes=5)).count()

                self.logger.warning('COUNTS: %d, %d, %d' % (actually_running_count, created_count, pending_count))

                remaining_instance_count = instance_count - running_count

                self.logger.warning('size: %s, instance_count: %d, running_count: %d, remaining_instance_count: %d' %
                                    (provider_size, instance_count, running_count, remaining_instance_count))

                for i in range(remaining_instance_count):
                    self.logger.warning('creating instance for size %s' % provider_size)
                    instance_name = '%s-%d' % (self.name, i)
                    ComputeInstance.create_with_provider(provider_configuration=provider_configuration, provider_size=provider_size,
                                                         authentication_method=self.authentication_method, compute_group=self)