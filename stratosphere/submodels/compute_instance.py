from annoying.fields import JSONField

from django.db import connection, models, transaction
from django.utils import timezone

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

import random

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..tasks import create_libcloud_node, terminate_libcloud_node
from ..util import decode_node_extra, schedule_random_default_delay


class ComputeInstanceBase(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        abstract = True

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

    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='instances')
    provider_image = models.ForeignKey('ProviderImage', related_name='instances')
    group = models.ForeignKey('ComputeGroup', related_name='instances')
    provider_size = models.ForeignKey('ProviderSize', related_name='instances')

    external_id = models.CharField(max_length=256, blank=True, null=True)
    name = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, null=True, blank=True)
    public_ips = JSONField()
    private_ips = JSONField()
    extra = JSONField()
    last_request_start_time = models.DateTimeField(blank=True, null=True)
    terminated = models.BooleanField(default=False)

    def schedule_create_libcloud_node_job(self):
        # delay a few seconds to avoid transaction conflicts
        schedule_random_default_delay(create_libcloud_node, self.pk)

    def terminate(self):
        with transaction.atomic():
            self.state = 'UNKNOWN'
            self.terminated = True
            self.last_request_start_time = timezone.now()
            self.save()

            connection.on_commit(lambda: schedule_random_default_delay(terminate_libcloud_node, self.pk))

    def to_libcloud_node(self):
        libcloud_node_args = {
            'id': self.external_id,
            'name': self.name,
            'state': NodeState.fromstring(self.state),
            'public_ips': self.public_ips,
            'private_ips': self.private_ips,
            'driver': self.provider_configuration.driver,
            'size': self.provider_size.to_libcloud_size(),
            'image': self.provider_image.to_libcloud_image(self.provider_configuration),
            'extra': decode_node_extra(self.extra)
        }
        return Node(**libcloud_node_args)
