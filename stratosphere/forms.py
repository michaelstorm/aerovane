from django.forms import ModelForm, PasswordInput
from django.forms.models import modelform_factory

from .models import *


Ec2ProviderConfigurationForm = modelform_factory(Ec2ProviderConfiguration, fields=())

LinodeProviderConfigurationForm = modelform_factory(LinodeProviderConfiguration, fields=('api_key',), widgets={'api_key': PasswordInput})

PasswordAuthenticationMethodForm = modelform_factory(PasswordAuthenticationMethod, fields=('name', 'password'), widgets={'password': PasswordInput})

KeyAuthenticationMethodForm = modelform_factory(KeyAuthenticationMethod, fields=('name', 'key'))
