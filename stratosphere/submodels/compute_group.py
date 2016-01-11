from django.db import models, transaction, OperationalError
from django.db.models import Q

from libcloud.compute.base import NodeAuthPassword, NodeAuthSSHKey
from libcloud.compute.types import NodeState

from polymorphic import PolymorphicModel

from ..models import ComputeInstance, PasswordAuthenticationMethod, ProviderConfiguration
from ..util import *

import json

import traceback


class BackoffError(Exception):
    pass


def update_distribution(func):
    def func_wrapper(self):
        def lock():
            with transaction.atomic():
                if self.updating_distribution:
                    raise BackoffError()
                else:
                    self.updating_distribution = True
                    self.save()

        def unlock():
            saved = False
            while not saved:
                try:
                    with transaction.atomic():
                        # don't re-save if deleted earlier
                        if ComputeGroup.objects.filter(pk=self.pk).exists():
                            self.updating_distribution = False
                            self.save()

                        saved = True

                except OperationalError:
                    pass

        try:
            call_with_retry(lock, (OperationalError, BackoffError), tries=10)
            func(self)
        finally:
            call_with_retry(unlock, (OperationalError, BackoffError), tries=10)

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
    provider_policy = models.TextField()
    updating_distribution = models.BooleanField(default=False)
    updating_distribution_time = models.DateTimeField(blank=True, null=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    authentication_method = models.ForeignKey('AuthenticationMethod', related_name='compute_groups')

    def _provider_policy_filtered(self):
        provider_policy_deserialized = json.loads(self.provider_policy)
        return provider_policy_deserialized

    def provider_states(self):
        provider_policy_filtered = self._provider_policy_filtered()
        provider_states_map = {}

        for provider_name in provider_policy_filtered:
            provider_configuration = ProviderConfiguration.objects.filter(provider_name=provider_name).first()
            provider_instances = self.instances.filter(provider_image__provider__name=provider_name)
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (ComputeInstance.PENDING, ComputeInstance.REBOOTING), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING),
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
    @retry((OperationalError, BackoffError), tries=10)
    def check_instance_distribution(self):
        self.logger.warning('Got lock')

        self.logger.warning('%s state: %s' % (self.name, self.state))

        instances_flat = list(self.instances.all())
        created_count = len(instances_flat)
        unknown_count = len(list(filter(lambda i: i.state not in (ComputeInstance.PENDING, ComputeInstance.RUNNING), instances_flat)))
        running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
        non_pending_count = len(list(filter(lambda i: i.state != ComputeInstance.PENDING, instances_flat)))
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

            self.logger.warning('created_count >= self.instance_count: %d >= %d: %s'
                              % (created_count, self.instance_count, created_count >= self.instance_count))

            self.logger.warning('created_count - unknown_count < self.instance_count: %d - %d < %d: %s'
                              % (created_count, unknown_count, self.instance_count, created_count - unknown_count < self.instance_count))

            if created_count >= self.instance_count and created_count - unknown_count < self.instance_count:
                bad_provider_ids = set([instance.provider_configuration.pk for instance in self.instances.filter(~Q(state=ComputeInstance.PENDING) & ~Q(state=ComputeInstance.RUNNING))])
                good_provider_ids = [provider.pk for provider in
                                     self.user_configuration.provider_configurations.exclude(pk__in=bad_provider_ids)]

                self.logger.warning('bad_provider_ids: %s' % bad_provider_ids)
                self.logger.warning('good_provider_ids: %s' % good_provider_ids)

                best_sizes = self._get_best_sizes(good_provider_ids)
                self._create_compute_instances(best_sizes)

            if running_count >= self.instance_count:
                for instance in non_running_instances:
                    self._destroy_instance(instance) # TODO currently no-op

    def _destroy_instance(self, instance):
        pass

    def create_instances(self):
        best_sizes = self._get_best_sizes()
        self._create_compute_instances(best_sizes)

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
        provider_policy_filtered = self._provider_policy_filtered()

        best_sizes = {}
        for provider_name in provider_policy_filtered:
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                available_sizes = []

                provider_image = provider_configuration.available_provider_images.filter(disk_image__disk_image_mappings__operating_system_image=self.image).first()
                if provider_image is not None:
                    available_sizes.extend(provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory))

                available_sizes.sort(key=lambda s: s.price)
                if len(available_sizes) > 0:
                    best_sizes[provider_name] = available_sizes[0]

        return best_sizes

    def _create_compute_instances(self, sizes):
        running_count = self.instances.filter(Q(state=ComputeInstance.PENDING) | Q(state=ComputeInstance.RUNNING)).count()
        remaining_instance_count = self.instance_count - running_count

        sizes_list = sorted(sizes.values(), key=lambda s: self.instances.filter(provider_configuration=s.provider_configuration).count())
        print('sizes_list', sizes_list)

        while remaining_instance_count > 0:
            for size in sizes_list:
                provider_configuration = size.provider_configuration
                provider_image = provider_configuration.available_provider_images.get(
                                        disk_image__disk_image_mappings__operating_system_image=self.image)

                provider_instance_count = int(remaining_instance_count/len(sizes)) * len(sizes)
                if provider_instance_count == 0 and remaining_instance_count > 0:
                    provider_instance_count = 1

                print('remaining_instance_count:', remaining_instance_count)
                print('provider_instance_count:', provider_instance_count, 'provider:', size.provider_configuration.provider_name)

                for i in range(provider_instance_count):
                    instance_name = '%s-%d' % (self.name, i)
                    ComputeInstance.create_with_provider(provider_configuration=provider_configuration, provider_image=provider_image, size=size,
                                                         name=instance_name, authentication_method=self.authentication_method)

                remaining_instance_count -= provider_instance_count