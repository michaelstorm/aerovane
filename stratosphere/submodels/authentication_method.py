from django.contrib.auth.models import User
from django.db import models

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

import uuid

from ..util import *


class AuthenticationMethod(PolymorphicModel, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='authentication_methods')
    name = models.CharField(max_length=64)


class PasswordAuthenticationMethod(AuthenticationMethod):
    class Meta:
        app_label = "stratosphere"

    password = models.CharField(max_length=256)

    def pretty_type(self):
        return 'Password'


class KeyAuthenticationMethod(AuthenticationMethod):
    class Meta:
        app_label = "stratosphere"

    key = models.TextField()

    def pretty_type(self):
        return 'Key'