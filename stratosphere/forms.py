from django.forms import ModelForm, PasswordInput
from django.forms.models import modelform_factory

from .models import *


class Ec2ProviderConfigurationForm(ModelForm):
    class Meta:
        model = Ec2ProviderConfiguration
        fields = ['access_key_id', 'secret_access_key']


class LinodeProviderConfigurationForm(ModelForm):
    class Meta:
        model = LinodeProviderConfiguration
        fields = ['api_key']


PasswordAuthenticationMethodForm = modelform_factory(PasswordAuthenticationMethod, fields=('name', 'password'), widgets={'password': PasswordInput})


class KeyAuthenticationMethodForm(ModelForm):
    class Meta:
        model = KeyAuthenticationMethod
        fields = ['name', 'key']