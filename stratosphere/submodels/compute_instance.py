from annoying.fields import JSONField

from datetime import timedelta

from django.db import connection, models, transaction
from django.db.models import Q
from django.utils import timezone

from libcloud.compute.base import Node
from libcloud.compute.types import NodeState

import random
import uuid

from .mixins import TrackSavedChanges

from ..tasks import create_libcloud_node, destroy_libcloud_node
from ..util import decode_node_extra, schedule_random_default_delay, thread_local


class ComputeInstanceBase(TrackSavedChanges, models.Model):
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='instances')
    provider_image = models.ForeignKey('ProviderImage', related_name='instances')
    group = models.ForeignKey('ComputeGroup', related_name='instances')
    provider_size = models.ForeignKey('ProviderSize', related_name='instances')

    created_at = models.DateTimeField(auto_now_add=True)
    external_id = models.CharField(max_length=256, blank=True, null=True)
    name = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, null=True, blank=True)
    public_ips = JSONField()
    private_ips = JSONField()
    extra = JSONField()

    destroyed = models.BooleanField(default=False) # mutually exclusive w/ failed
    destroyed_at = models.DateTimeField(null=True, blank=True)

    failed = models.BooleanField(default=False) # mutually exclusive w/ destroyed
    failed_at = models.DateTimeField(null=True, blank=True)
    failure_ignored = models.BooleanField(default=False)

    @classmethod
    def destroyed_instances_query(cls):
        return Q(destroyed=True)

    @classmethod
    def failed_instances_query(cls):
        return Q(failed=True)

    @classmethod
    def unavailable_instances_query(cls):
        return cls.destroyed_instances_query() | cls.failed_instances_query()

    @classmethod
    def unignored_failed_instances_query(cls):
        return cls.failed_instances_query() & Q(failure_ignored=False)

    @classmethod
    def running_instances_query(cls):
        state_running = Q(state=ComputeInstanceBase.RUNNING)
        not_unavailable = ~cls.unavailable_instances_query()
        return state_running & not_unavailable

    @classmethod
    def pending_instances_query(cls):
        # state__in=[None] returns an empty list no matter what
        # TODO include REBOOTING?
        state_pending = Q(state=None) | Q(state='PENDING')
        not_unavailable = ~cls.unavailable_instances_query()
        return state_pending & not_unavailable

    @classmethod
    def handle_pre_save(cls, sender, instance, raw, using, update_fields, **kwargs):
        old_instance = cls.objects.filter(pk=instance.id).first() if instance.id is not None else None
        if old_instance is None or instance.state != old_instance.state:
            instance.last_state_update_time = timezone.now()

    @classmethod
    def handle_post_save(cls, sender, created, instance, **kwargs):
        if created:
            schedule_random_default_delay(create_libcloud_node, instance.pk)

    # TODO fix this so it doesn't hit the database again
    def _is_in_state(self, state_query):
        instances = self.__class__.objects.filter(state_query & Q(pk=self.pk))
        return instances.exists()

    def is_running(self):
        state_query = self.__class__.running_instances_query()
        return self._is_in_state(state_query)

    def is_pending(self):
        state_query = self.__class__.pending_instances_query()
        return self._is_in_state(state_query)

    def is_destroyed(self):
        state_query = self.__class__.destroyed_instances_query()
        return self._is_in_state(state_query)

    def is_failed(self):
        state_query = self.__class__.failed_instances_query()
        return self._is_in_state(state_query)

    @thread_local(DB_OVERRIDE='serializable')
    def destroy(self):
        with transaction.atomic():
            self.destroyed = True
            self.destroyed_at = timezone.now() # TODO make this consistent if a group of instances are destroyed?
            self.save()

            connection.on_commit(lambda: schedule_random_default_delay(destroy_libcloud_node, self.pk))

    def admin_url(self):
        return self.provider_configuration.admin_url(self)

    def to_libcloud_node(self):
        libcloud_node_args = {
            'id': self.external_id,
            'name': self.name,
            'state': None if self.state is None else NodeState.fromstring(self.state),
            'public_ips': self.public_ips,
            'private_ips': self.private_ips,
            'driver': self.provider_configuration.driver,
            'size': self.provider_size.to_libcloud_size(),
            'image': self.provider_image.to_libcloud_image(self.provider_configuration),
            'extra': decode_node_extra(self.extra)
        }
        return Node(**libcloud_node_args)