from django.forms import ModelForm, PasswordInput, HiddenInput
from django.forms.models import modelform_factory

from .models import *


Ec2ProviderConfigurationForm = modelform_factory(Ec2ProviderConfiguration, fields=('user_configuration',), widgets={'user_configuration': HiddenInput})

LinodeProviderConfigurationForm = modelform_factory(LinodeProviderConfiguration, fields=('api_key',), widgets={'api_key': PasswordInput, 'user_configuration': HiddenInput})

PasswordAuthenticationMethodForm = modelform_factory(PasswordAuthenticationMethod,
                                                     fields=('name', 'password'),
                                                     widgets={'password': PasswordInput(attrs={'autocomplete':'new-password'}),
                                                               'user_configuration': HiddenInput})

KeyAuthenticationMethodForm = modelform_factory(KeyAuthenticationMethod, fields=('name', 'key'), widgets={'user_configuration': HiddenInput})
