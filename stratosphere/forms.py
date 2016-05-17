from django import forms
from django.forms import ModelForm, PasswordInput, HiddenInput
from django.forms.models import modelform_factory

from .models import *


Ec2ProviderConfigurationForm = modelform_factory(Ec2ProviderConfiguration, fields=('user',), widgets={'user': HiddenInput})

LinodeProviderConfigurationForm = modelform_factory(LinodeProviderConfiguration, fields=('api_key',), widgets={'api_key': PasswordInput, 'user': HiddenInput})

PasswordAuthenticationMethodForm = modelform_factory(PasswordAuthenticationMethod,
                                                     fields=('name', 'password'),
                                                     widgets={'password': PasswordInput(attrs={'autocomplete':'new-password'}),
                                                               'user': HiddenInput})

KeyAuthenticationMethodForm = modelform_factory(KeyAuthenticationMethod, fields=('name', 'key'), widgets={'user': HiddenInput})


class SignupForm(forms.Form):
    first_name = forms.CharField(max_length=30, label='First name')
    last_name = forms.CharField(max_length=30, label='Last name')

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
