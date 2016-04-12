from django.db import models

from libcloud.compute.base import NodeLocation
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

from stratosphere.models import ProviderConfiguration


class LinodeProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

    api_key = models.CharField(max_length=128)

    def create_driver(self):
        cls = get_driver(LibcloudProvider.LINODE)
        return cls(self.api_key)

    def get_available_sizes(self, provider_image, cpu, memory):
        return self.provider_sizes.filter(cpu__gte=cpu, ram__gte=memory)

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        location = NodeLocation(id='2', name='Dallas, TX, USA', country='USA', driver=self.driver)
        return super(LinodeProviderConfiguration, self).create_libcloud_node(name=name, libcloud_image=libcloud_image,
                        libcloud_size=libcloud_size, libcloud_auth=libcloud_auth, location=location)

    def _get_credentials_dict(self):
        return {'api_key': self.api_key}