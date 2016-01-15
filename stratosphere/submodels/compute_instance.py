from annoying.fields import JSONField

from datetime import datetime

from django.db import connection, models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

from save_the_change.mixins import SaveTheChange

from ..models import PasswordAuthenticationMethod
from ..tasks import check_instance_distribution, create_compute_instance, terminate_libcloud_node
from ..util import decode_node_extra


class ComputeInstance(models.Model, SaveTheChange):
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
    state = models.CharField(max_length=16, choices=STATE_CHOICES, null=True, blank=True)
    public_ips = JSONField()
    private_ips = JSONField()
    provider_size = models.ForeignKey('ProviderSize', related_name='instances')
    extra = JSONField()
    last_request_start_time = models.DateTimeField(blank=True, null=True)
    terminated = models.BooleanField(default=False)

    @staticmethod
    def create_with_provider(provider_configuration, provider_size, authentication_method, compute_group):
        create_compute_instance.delay(provider_configuration.pk, provider_size.pk,
                                      authentication_method.pk, compute_group.pk)

    def terminate(self):
        with transaction.atomic():
            self.state = ComputeInstance.UNKNOWN
            self.terminated = True
            self.last_request_start_time = timezone.now()
            self.save()

            connection.on_commit(lambda: terminate_libcloud_node.delay(self.pk))

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
