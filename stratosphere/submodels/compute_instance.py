from annoying.fields import JSONField

from datetime import datetime

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

from ..util import *


class ComputeInstance(models.Model):
    class Meta:
        app_label = "stratosphere"

    RUNNING = 'RUNNING'
    REBOOTING = 'REBOOTING'
    TERMINATED = 'TERMINATED'
    PENDING = 'PENDING'
    STOPPED = 'STOPPED'
    SUSPENDED = 'SUSPENDED'
    PAUSED = 'PAUSED'
    ERROR = 'ERROR'
    UNKNOWN = 'UNKNOWN'

    STATE_CHOICES = (
        (RUNNING, 'Running'),
        (REBOOTING, 'Rebooting'),
        (TERMINATED, 'Terminated'),
        (PENDING, 'Pending'),
        (STOPPED, 'Stopped'),
        (SUSPENDED, 'Suspended'),
        (PAUSED, 'Paused'),
        (ERROR, 'Error'),
        (UNKNOWN, 'Unknown'),
    )

    external_id = models.CharField(max_length=256)
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='instances')
    provider_image = models.ForeignKey('ProviderImage', related_name='instances')
    group = models.ForeignKey('ComputeGroup', related_name='instances')
    name = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=UNKNOWN)
    target_state = models.CharField(max_length=16, choices=STATE_CHOICES, default=UNKNOWN)
    target_state_time = models.DateTimeField()
    public_ips = JSONField()
    private_ips = JSONField()
    size = models.ForeignKey('ProviderSize', related_name='instances')
    extra = JSONField()

    @classmethod
    def _create_libcloud_node(provider_configuration, provider_image, size, name, authentication_method):
        if isinstance(authentication_method, PasswordAuthenticationMethod):
            libcloud_auth = NodeAuthPassword(authentication_method.password)
        else:
            libcloud_auth = NodeAuthSSHKey(authentication_method.key)

        libcloud_size = size.to_libcloud_size()
        libcloud_image = provider_image.to_libcloud_image(provider_configuration)

        return provider_configuration.create_libcloud_node(name=name, libcloud_image=libcloud_image, libcloud_size=libcloud_size,
                                                           libcloud_auth=libcloud_auth)

    @classmethod
    def create_with_provider(provider_configuration, provider_image, size, name, authentication_method, compute_group):
        compute_instance = ComputeInstance.objects.create(name=libcloud_node.name, provider_image=provider_image, group=compute_group,
                                                          size=provider_size, extra={}, provider_configuration=provider_configuration,
                                                          state=ComputeInstance.PENDING, target_state=ComputeInstance.RUNNING,
                                                          target_state_time=datetime.now())

        ComputeInstance._create_libcloud_node(provider_configuration=provider_configuration, provider_image=provider_image, size=size,
                                              name=name, authentication_method=authentication_method)

        return compute_instance

    def to_libcloud_node(self):
        return Node(id=self.external_id, name=self.name, state=NodeState.fromstring(self.state), public_ips=self.public_ips,
                    private_ips=self.private_ips, driver=self.provider_configuration.driver, size=self.size.to_libcloud_size(),
                    image=self.provider_image.to_libcloud_image(self.provider_configuration), extra=decode_node_extra(self.extra))


@receiver(post_save, sender=ComputeInstance)
def check_instance_distribution(sender, created, instance, **kwargs):
    compute_group = instance.group
    if not compute_group.updating_distribution:
        compute_group.check_instance_distribution()
