from django.db import models, transaction, OperationalError

from libcloud.compute.base import NodeAuthPassword, NodeAuthSSHKey
from libcloud.compute.types import NodeState

from polymorphic import PolymorphicModel

from ..util import *

import json

import traceback


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
            provider_instances = self.instances.filter(provider_image__provider_configuration__provider_name=provider_name)
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (ComputeInstance.PENDING, ComputeInstance.REBOOTING), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING),
                                               provider_instances)))

            provider_states_map[provider_name] = {
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.pretty_name(),
            }

        return provider_states_map

    def check_instance_distribution(self):
        try:
            with transaction.atomic():
                if self.updating_distribution:
                    return
                else:
                    self.updating_distribution = True
                    self.save()

        except OperationalError as e:
            print('OperationalError', e)
            return

        try:
            self.logger.debug('%s state: %s' % (self.name, self.state))

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
                    print(self.delete())
            else:
                if self.state == self.PENDING and non_pending_count >= self.instance_count:
                    self.state = self.RUNNING

                self.logger.debug('created_count >= self.instance_count: %d >= %d: %s'
                                  % (created_count, self.instance_count, created_count >= self.instance_count))

                self.logger.debug('created_count - unknown_count < self.instance_count: %d - %d < %d: %s'
                                  % (created_count, unknown_count, self.instance_count, created_count - unknown_count < self.instance_count))

                if created_count >= self.instance_count and created_count - unknown_count < self.instance_count:
                    bad_provider_ids = set([instance.provider_image.provider_configuration.pk for instance in self.instances.all()])
                    good_provider_ids = [provider.pk for provider in ProviderConfiguration.objects.exclude(pk__in=bad_provider_ids)]

                    new_size = self._get_best_size(good_provider_ids)
                    self._create_compute_instances(new_size)

                if running_count >= self.instance_count:
                    for instance in non_running_instances:
                        self._destroy_instance(instance)

        finally:
            saved = False

            while not saved:
                try:
                    # don't re-save if deleted earlier
                    if ComputeGroup.objects.filter(pk=self.pk).exists():
                        self.updating_distribution = False
                        self.save()

                    saved = True

                except OperationalError:
                    pass

    def _create_compute_instance_entry(self, provider_image, provider_size, libcloud_node):
        return ComputeInstance.objects.create(external_id=libcloud_node.id, provider_image=provider_image, group=self, name=libcloud_node.name,
                                              state=NodeState.tostring(libcloud_node.state), public_ips=json.loads(json.dumps(libcloud_node.public_ips)),
                                              private_ips=json.loads(json.dumps(libcloud_node.private_ips)), size=provider_size,
                                              extra=json.loads(json.dumps(libcloud_node.extra, cls=NodeJSONEncoder)))

    def _destroy_instance(self, instance):
        pass

    def create_instances(self):
        selected_size = self._get_best_size()
        self._create_compute_instances(selected_size)

    def terminate(self):
        self.state = self.TERMINATED
        self.save()

        for instance in self.instances.all():
            try:
                instance.provider_image.provider_configuration.driver.destroy_node(instance.to_libcloud_node())
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

    def _get_best_size(self, allowed_provider_ids=None):
        provider_policy_filtered = self._provider_policy_filtered()

        available_sizes = []
        print('provider_policy_filtered:', provider_policy_filtered)
        for provider_name in provider_policy_filtered:
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            print('allowed_provider_ids:', allowed_provider_ids, 'provider_configuration.pk:', provider_configuration.pk)
            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                provider_image = provider_configuration.provider_images.get(disk_image__operating_system_images=self.image)
                available_sizes.extend(provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory))

        available_sizes.sort(key=lambda s: s.price)
        return available_sizes[0]

    def _create_compute_instances(self, selected_size):
        provider_configuration = selected_size.provider_configuration
        provider_image = provider_configuration.provider_images.get(disk_image__operating_system_images=self.image)

        for i in range(self.instance_count):
            if isinstance(self.authentication_method, PasswordAuthenticationMethod):
                libcloud_auth = NodeAuthPassword(self.authentication_method.password)
            else:
                libcloud_auth = NodeAuthSSHKey(self.authentication_method.key)

            libcloud_node = provider_configuration.create_libcloud_node(name='%s-%d' % (self.name, i), libcloud_image=provider_image.to_libcloud_image(),
                                                                        libcloud_size=selected_size.to_libcloud_size(), libcloud_auth=libcloud_auth)
            self._create_compute_instance_entry(provider_image, selected_size, libcloud_node)
