from django.db import models
from django.dispatch import receiver

from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

from stratosphere.models import Provider, ProviderConfiguration, ProviderCredentialSet

import os
import uuid


class AzureProviderCredentialSet(ProviderCredentialSet):
    class Meta:
        app_label = "stratosphere"

    subscription_id = models.CharField(max_length=128)
    management_certificate = models.TextField()


class AzureProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

    cloud_service_name = models.CharField(max_length=24)
    location = models.CharField(max_length=32)

    ecus_by_id = {
        'ExtraSmall': 1,
        'Small': 1,
        'Medium': 2,
        'Large': 4,
        'ExtraLarge': 8
    }

    CERTIFICATES_DIRECTORY = 'tmp/azure_user_certificates'

    @staticmethod
    def create_account(user, subscription_id, management_certificate, location):
        provider_credential_set = AzureProviderCredentialSet.objects.create(
                                    subscription_id=subscription_id,
                                    management_certificate=management_certificate)

        provider_name = 'azure_%s' % location.lower().replace(' ', '_')
        provider = Provider.objects.get(name=provider_name)

        provider_configuration = AzureProviderConfiguration.objects.create(
            provider=provider,
            provider_name=provider_name,
            provider_credential_set=provider_credential_set,
            user=user,
            location=location,
            cloud_service_name=str(uuid.uuid4()).replace('-', '')[:24])

        provider_configuration.driver.ex_create_cloud_service(name=provider_configuration.cloud_service_name, location=location)

    @staticmethod
    def _filter_driver_sizes(driver_sizes):
        return driver_sizes

    @property
    def certificates_file_path(self):
        return os.path.join(self.CERTIFICATES_DIRECTORY, str(self.pk))

    def _write_certificate_file(self):
        os.makedirs(self.CERTIFICATES_DIRECTORY, exist_ok=True)
        file = open(self.certificates_file_path, 'w')

        file.truncate()
        file.write(self.provider_credential_set.management_certificate)
        file.close()

    def _list_nodes(self):
        return self.driver.list_nodes(self.cloud_service_name)

    def create_driver(self):
        self._write_certificate_file()

        cls = get_driver(LibcloudProvider.AZURE)
        return cls(subscription_id=self.provider_credential_set.subscription_id, key_file=self.certificates_file_path)

    def get_available_sizes(self, provider_image, cpu, memory):
        sizes = self.provider_sizes.filter(cpu__gte=cpu, ram__gte=memory)
        return list(sizes)

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        return self.driver.create_node(name=name, image=libcloud_image, size=libcloud_size, auth=libcloud_auth,
                                       ex_cloud_service_name=str(self.cloud_service_name), **extra_args)

    def _get_credentials_dict(self):
        return {'subscription_id': self.provider_credential_set.subscription_id,
                'management_certificate': self.provider_credential_set.management_certificate}

    def _get_driver_images(self, include_public):
        return self.driver.list_images()

    def admin_url(self, compute_instance=None):
        return "https://azure.microsoft.com"

    def image_is_public(self, provider_image):
        return provider_image.extra['category'] == 'Public'

    def init(self):
        self.cloud_service_name = str(uuid.uuid4()).replace('-', '')[:24]
        self.save()
