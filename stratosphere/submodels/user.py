from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

import hashlib

from ..util import *


class UserConfiguration(models.Model):
    class Meta:
        app_label = "stratosphere"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuration')

    def avatar_url(self):
        return 'https://www.gravatar.com/avatar/%s?s=48' % hashlib.md5(self.user.email.strip().lower().encode('utf-8')).hexdigest()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_configuration_for_new_user(sender, created, instance, **kwargs):
    if created:
        UserConfiguration.objects.create(user=instance)