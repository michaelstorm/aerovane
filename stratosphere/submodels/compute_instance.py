from annoying.fields import JSONField

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

from ..util import *


class ComputeInstance(models.Model):
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
    provider_image = models.ForeignKey('ProviderImage', related_name='instances')
    group = models.ForeignKey('ComputeGroup', related_name='instances')
    name = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=UNKNOWN)
    public_ips = JSONField()
    private_ips = JSONField()
    size = models.ForeignKey('ProviderSize', related_name='instances')
    extra = JSONField()

    def to_libcloud_node(self):
        return Node(id=self.external_id, name=self.name, state=NodeState.fromstring(self.state), public_ips=self.public_ips,
                    private_ips=self.private_ips, driver=self.provider_image.provider_configuration.driver, size=self.size.to_libcloud_size(),
                    image=self.provider_image.to_libcloud_image(), extra=decode_node_extra(self.extra))


@receiver(post_save, sender=ComputeInstance)
def check_instance_distribution(sender, created, instance, **kwargs):
    compute_group = instance.group
    if not compute_group.updating_distribution:
        compute_group.check_instance_distribution()
