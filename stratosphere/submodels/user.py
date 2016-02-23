from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

import hashlib

from save_the_change.mixins import SaveTheChange

from ..models import InstanceStatesSnapshot
from ..util import *


class UserConfiguration(models.Model, SaveTheChange):
    class Meta:
        app_label = "stratosphere"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuration')

    def avatar_url(self):
        return 'https://www.gravatar.com/avatar/%s?s=48' % hashlib.md5(self.user.email.strip().lower().encode('utf-8')).hexdigest()

    def create_phantom_instance_states_snapshot(self):
        if self._state.db != 'read_committed':
            instance = UserConfiguration.objects.using('read_committed').get(pk=self.pk)
            return instance.create_phantom_instance_states_snapshot()
        else:
            now = timezone.now()
            args = {
                'user_configuration': self,
                'time': now,
                'running': 0,
                'rebooting': 0,
                'terminated': 0,
                'pending': 0,
                'stopped': 0,
                'suspended': 0,
                'paused': 0,
                'error': 0,
                'unknown': 0,
            }

            group_snapshots = [g.create_phantom_instance_states_snapshot(now) for g in self.compute_groups.using('read_committed').all()]
            for group_snapshot in group_snapshots:
                args['running'] += group_snapshot.running
                args['rebooting'] += group_snapshot.rebooting
                args['terminated'] += group_snapshot.terminated
                args['pending'] += group_snapshot.pending
                args['stopped'] += group_snapshot.stopped
                args['suspended'] += group_snapshot.suspended
                args['paused'] += group_snapshot.paused
                args['error'] += group_snapshot.error
                args['unknown'] += group_snapshot.unknown

            return InstanceStatesSnapshot(**args), group_snapshots

    def take_instance_states_snapshot(self):
        with transaction.atomic():
            user_snapshot, group_snapshots = self.create_phantom_instance_states_snapshot()

            user_snapshot.save(using='read_committed')

            for group_snapshot in group_snapshots:
                group_snapshot.user_snapshot = user_snapshot
                group_snapshot.save(using='read_committed')


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_configuration_for_new_user(sender, created, instance, **kwargs):
    if created:
        UserConfiguration.objects.create(user=instance)