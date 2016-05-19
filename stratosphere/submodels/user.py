from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, User
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

import hashlib
import uuid

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..util import *



class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password,
                     is_staff, is_superuser, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        now = timezone.now()
        email = self.normalize_email(email)
        user = self.model(email=email,
                          is_staff=is_staff, is_active=True,
                          is_superuser=is_superuser,
                          date_joined=now, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        return self._create_user(email, password, False, False,
                                 **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        return self._create_user(email, password, True, True,
                                 **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    A class implementing a fully featured User model with
    admin-compliant permissions.
    """
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        app_label = "stratosphere"

    ###################
    # standard fields #
    ###################

    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    email = models.EmailField(_('email address'), max_length=255, unique=True, db_index=True)
    is_staff = models.BooleanField(_('staff status'), default=False,
        help_text=_('Designates whether the user can log into this admin '
                    'site.'))
    is_active = models.BooleanField(_('active'), default=True,
        help_text=_('Designates whether this user should be treated as '
                    'active. Unselect this instead of deleting accounts.'))
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    ####################
    # standard methods #
    ####################

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        "Returns the short name for the user."
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    ##################
    # custom methods #
    ##################

    def avatar_url(self):
        return 'https://www.gravatar.com/avatar/%s?s=48' % hashlib.md5(self.email.strip().lower().encode('utf-8')).hexdigest()

    def create_phantom_instance_states_snapshot(self):
        from ..models import InstanceStatesSnapshot

        now = timezone.now()
        args = {
            'user': self,
            'time': now,
            'pending': 0,
            'running': 0,
            'failed': 0,
        }

        group_snapshots = [g.create_phantom_instance_states_snapshot(now) for g in self.compute_groups.all()]
        for group_snapshot in group_snapshots:
            args['pending'] += group_snapshot.pending
            args['running'] += group_snapshot.running
            args['failed'] += group_snapshot.failed

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
            return {state: getattr(snapshot, state) for state in ('pending', 'running', 'failed')}

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