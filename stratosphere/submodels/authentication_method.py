from django.db import models

from polymorphic import PolymorphicModel

from ..util import *


class AuthenticationMethod(PolymorphicModel):
    class Meta:
        app_label = "stratosphere"

    user_configuration = models.ForeignKey('UserConfiguration', related_name='authentication_methods')
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