from django.forms import ModelForm

from .models import *


class Ec2ProviderConfigurationForm(ModelForm):
    class Meta:
        model = Ec2ProviderConfiguration
        fields = ['access_key_id', 'secret_access_key']


class LinodeProviderConfigurationForm(ModelForm):
    class Meta:
        model = LinodeProviderConfiguration
        fields = ['api_key']
