from django import forms
from django.conf import settings
from django.forms import ModelForm, PasswordInput, HiddenInput
from django.forms.models import modelform_factory

from .models import *


AWSProviderConfigurationForm = modelform_factory(AWSProviderConfiguration, fields=('user',), widgets={'user': HiddenInput})

LinodeProviderConfigurationForm = modelform_factory(LinodeProviderConfiguration, fields=('api_key',), widgets={'api_key': PasswordInput, 'user': HiddenInput})

PasswordAuthenticationMethodForm = modelform_factory(PasswordAuthenticationMethod,
                                                     fields=('name', 'password'),
                                                     widgets={'password': PasswordInput(attrs={'autocomplete':'new-password'}),
                                                              'user': HiddenInput})

KeyAuthenticationMethodForm = modelform_factory(KeyAuthenticationMethod, fields=('name', 'key'), widgets={'user': HiddenInput})


class SignupForm(forms.Form):
    beta_key = forms.CharField(label='Beta key', widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))
    first_name = forms.CharField(max_length=30, label='First name')
    last_name = forms.CharField(max_length=30, label='Last name')

    def clean_beta_key(self):
        value = self.cleaned_data['beta_key'].strip().lower()
        if not settings.DEBUG:
            beta_key = BetaKey.objects.filter(value=value).first()
            if beta_key is None:
                raise forms.ValidationError('This beta key is not recognized.')
            elif beta_key.user is not None:
                raise forms.ValidationError('This beta key is already is use.')
        return value

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()

        if not settings.DEBUG:
            beta_key_value = self.cleaned_data['beta_key']
            beta_key = BetaKey.objects.filter(value=beta_key_value).first()
            beta_key.user = user
            beta_key.save()
