from annoying.fields import JSONField

from datetime import timedelta

from django.db import connection, models, transaction
from django.db.models import Q
from django.utils import timezone

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

import random

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..tasks import terminate_libcloud_node
from ..util import decode_node_extra, schedule_random_default_delay, thread_local


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
    last_state_update_time = models.DateTimeField()
    terminated = models.BooleanField(default=False)

    # TODO include REBOOTING here?
    # state__in=[None] returns empty list no matter what
    pending_states_query = Q(state='PENDING') | Q(state=None)

    @classmethod
    def running_instances_query(cls, now):
        two_minutes_ago = now - timedelta(minutes=2)
        return Q(state=ComputeInstanceBase.RUNNING, last_state_update_time__gt=two_minutes_ago)

    @classmethod
    def pending_instances_query(cls, now):
        two_minutes_ago = now - timedelta(minutes=2)
        return ComputeInstanceBase.pending_states_query & Q(last_state_update_time__gt=two_minutes_ago)

    @classmethod
    def terminated_instances_query(cls, now):
        not_pending_or_running = ~(cls.running_instances_query(now) | cls.pending_instances_query(now))
        return not_pending_or_running & ~Q(terminated=True)

    # TODO fix this so it doesn't hit the database again
    def _is_in_state(self, state_query):
        instances = self.__class__.objects.filter(state_query & Q(pk=self.pk))
        return instances.exists()

    def is_running(self, now):
        state_query = self.__class__.running_instances_query(now)
        return self._is_in_state(state_query)

    def is_pending(self, now):
        state_query = self.__class__.pending_instances_query(now)
        return self._is_in_state(state_query)

    def is_terminated(self, now):
        state_query = self.__class__.terminated_instances_query(now)
        return self._is_in_state(state_query)

    @thread_local(DB_OVERRIDE='serializable')
    def terminate(self):
        with transaction.atomic():
            self.terminated = True
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