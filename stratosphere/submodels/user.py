from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

import hashlib
import uuid

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..models import InstanceStatesSnapshot
from ..util import *


class UserConfiguration(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuration')

    def avatar_url(self):
        return 'https://www.gravatar.com/avatar/%s?s=48' % hashlib.md5(self.user.email.strip().lower().encode('utf-8')).hexdigest()

    def create_phantom_instance_states_snapshot(self):
        now = timezone.now()
        args = {
            'user_configuration': self,
            'time': now,
            'pending': 0,
            'running': 0,
            'terminated': 0,
        }

        group_snapshots = [g.create_phantom_instance_states_snapshot(now) for g in self.compute_groups.all()]
        for group_snapshot in group_snapshots:
            args['pending'] += group_snapshot.pending
            args['running'] += group_snapshot.running
            args['terminated'] += group_snapshot.terminated

        return InstanceStatesSnapshot(**args), group_snapshots

    def take_instance_states_snapshot(self):
        with transaction.atomic():
            user_snapshot, group_snapshots = self.create_phantom_instance_states_snapshot()

            user_snapshot.save()

            for group_snapshot in group_snapshots:
                group_snapshot.user_snapshot = user_snapshot
                group_snapshot.save()

    def take_instance_states_snapshot_if_changed(self):
        def snapshots_values(snapshot):
            return {state: getattr(snapshot, state) for state in ('pending', 'running', 'terminated')}

        def snapshot_values_equal(first, second):
            if first is None or second is None:
                return first is None and second is None
            else:
                return snapshots_values(first) == snapshots_values(second)

        user_snapshot, group_snapshots = self.create_phantom_instance_states_snapshot()
        last_user_snapshot = self.instance_states_snapshots.order_by('-time').first()

        not_equal = not snapshot_values_equal(user_snapshot, last_user_snapshot)

        if not not_equal and last_user_snapshot is not None:
            group_snapshots_map = {gs.group.pk: gs for gs in group_snapshots}
            last_group_snapshots_map = {gs.group.pk: gs for gs in last_user_snapshot.group_snapshots.all()}

            all_group_ids = set(list(group_snapshots_map.keys()) + list(last_group_snapshots_map.keys()))
            for group_id in all_group_ids:
                if not snapshot_values_equal(group_snapshots_map.get(group_id),
                                             last_group_snapshots_map.get(group_id)):
                    not_equal = True
                    break

        if not_equal:
            print('creating snapshot')
            with transaction.atomic():
                user_snapshot.save()

                for group_snapshot in group_snapshots:
                    group_snapshot.user_snapshot = user_snapshot
                    group_snapshot.save()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_configuration_for_new_user(sender, created, instance, **kwargs):
    if created:
        UserConfiguration.objects.create(user=instance)