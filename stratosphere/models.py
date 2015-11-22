from annoying.fields import JSONField

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver

from multicloud.celery import app

from polymorphic import PolymorphicModel

import json
import math


PROVIDER_CHOICES = (
    ('aws', 'Amazon Web Services'),
    ('azure', 'Microsoft Azure'),
    ('linode', 'Linode'),
    ('digitalocean', 'DigitalOcean'),
    ('softlayer', 'SoftLayer'),
    ('cloudsigma', 'CloudSigma'),
    ('google', 'Google App Engine'),
)


CLOUD_PROVIDER_DRIVERS = {}


class UserConfiguration(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuration')


class Image(PolymorphicModel):
    name = models.CharField(max_length=128)

    def __str__(self):
        return self.name


class DiskImage(Image):
    pass


class OperatingSystemImage(Image):
    disk_images = models.ManyToManyField(DiskImage, related_name='operating_system_images')


class ProviderImage(models.Model):
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_images')
    disk_image = models.ForeignKey(DiskImage, related_name='provider_images')
    image_id = models.CharField(max_length=256)
    name = models.CharField(max_length=256)
    extra = JSONField()


class ProviderSize(models.Model):
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_sizes')
    external_id = models.CharField(max_length=256)
    name = models.CharField(max_length=256)
    price = models.FloatField()
    ram = models.IntegerField()
    disk = models.IntegerField()
    bandwidth = models.IntegerField(null=True, blank=True)
    extra = JSONField()


class ProviderConfiguration(PolymorphicModel):
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey(UserConfiguration, null=True, blank=True, related_name='provider_configurations')

    default_operating_systems = {
        'Ubuntu 14.04': {
            'aws': 'ami-84bba3c1',
            'linode': '124'
        }
    }

    @property
    def driver(self):
        if self.provider_name not in CLOUD_PROVIDER_DRIVERS:
            CLOUD_PROVIDER_DRIVERS[self.provider_name] = self.create_driver()

        return CLOUD_PROVIDER_DRIVERS[self.provider_name]

    def load_available_sizes(self):
        driver_sizes = self.driver.list_sizes()
        for driver_size in driver_sizes:
            if ProviderSize.objects.filter(provider_configuration=self, external_id=driver_size.id).first() is None:
                ProviderSize.objects.create(provider_configuration=self, external_id=driver_size.id, name=driver_size.name, price=driver_size.price,
                                            ram=driver_size.ram, disk=driver_size.disk, bandwidth=driver_size.bandwidth,
                                            extra=json.loads(json.dumps(driver_size.extra)))

    def load_available_images(self):
        print('Querying images for provider %s' % self.provider_name)
        driver_images = self.driver.list_images()
        print('Retrieved %d images' % len(driver_images))

        print('Creating ProviderImages...')
        filtered_driver_images = driver_images[:10] # TODO remove driver images limit

        for os_name in self.default_operating_systems:
            driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
            if driver_image_id is not None:
                if len([i for i in filtered_driver_images if i.id == driver_image_id]) == 0:
                    filtered_driver_images.append([i for i in driver_images if i.id == driver_image_id][0])

        provider_images = []
        for driver_image in filtered_driver_images:
            provider_image = ProviderImage.objects.filter(provider_name=self.provider_name, image_id=driver_image.id).first()

            if provider_image is None:
                provider_images.append(ProviderImage(provider_name=self.provider_name, image_id=driver_image.id,
                                                     extra=json.loads(json.dumps(driver_image.extra))))

        ProviderImage.objects.bulk_create(provider_images)
        print('Created %d ProviderImages' % len(provider_images))

        print('Creating Images...')
        image_count = 0
        for driver_image in filtered_driver_images: # TODO remove driver images limit
            image_name = driver_image.name if driver_image.name is not None else '<%s>' % driver_image.id
            disk_image = DiskImage.objects.filter(name=image_name).first()

            if disk_image is None:
                disk_image = DiskImage.objects.create(name=image_name)
                image_count += 1

                provider_image = ProviderImage.objects.filter(provider_name=self.provider_name, image_id=driver_image.id).first()
                disk_image.provider_images.add(provider_image)

        for os_name in self.default_operating_systems:
            print('os_name:', os_name)
            driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
            if driver_image_id is not None:
                provider_image = ProviderImage.objects.filter(provider_name=self.provider_name, image_id=driver_image_id).first()
                print('provider_image', provider_image)

                os_image = OperatingSystemImage.objects.filter(name=os_name).first()
                print('os_image', os_image)
                if os_image is None:
                    os_image = OperatingSystemImage.objects.create(name=os_name)

                disk_image = provider_image.disk_image
                print('disk_image', disk_image)
                os_image.disk_images.add(disk_image)


class Ec2ProviderConfiguration(ProviderConfiguration):
    access_key_id = models.CharField(max_length=128)
    secret_access_key = models.CharField(max_length=128)

    def create_driver(self):
        cls = get_driver(Provider.EC2)
        return cls(self.access_key_id, self.secret_access_key, region='us-west-1')


class LinodeProviderConfiguration(ProviderConfiguration):
    api_key = models.CharField(max_length=128)

    def create_driver(self):
        cls = get_driver(Provider.LINODE)
        return cls(self.api_key)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_configuration_for_new_user(sender, created, instance, **kwargs):
    if created:
        UserConfiguration.objects.create(user=instance)


class ComputeGroup(PolymorphicModel):
    user_configuration = models.ForeignKey(UserConfiguration, related_name='compute_groups')
    instance_count = models.IntegerField()
    cpu = models.IntegerField()
    memory = models.IntegerField()
    name = models.CharField(max_length=128)
    provider_policy = models.TextField()

    def _provider_policy_filtered(self):
        provider_policy_deserialized = json.loads(self.provider_policy)
        return provider_policy_deserialized
        # return {provider_name: provider_policy_deserialized[provider_name] for provider_name in provider_policy_deserialized
        #         if provider_name in settings.CLOUD_PROVIDERS}

    def provider_states(self):
        provider_policy_filtered = self._provider_policy_filtered()
        provider_states_map = {}

        for provider_name in provider_policy_filtered:
            provider_instances = self.instances.filter(provider=provider_name)
            if len(provider_instances) > 0:
                provider_states_map[provider_instances[0].provider] = len(provider_instances)

        return provider_states_map


class ImageComputeGroup(ComputeGroup):
    image = models.ForeignKey(DiskImage, related_name='compute_groups')


class OperatingSystemComputeGroup(ComputeGroup):
    image = models.ForeignKey(OperatingSystemImage, related_name='compute_groups')

    def create_instances(self):
        provider_policy_filtered = self._provider_policy_filtered()
        instances_created = 0

        for provider_name in provider_policy_filtered:
            policy = provider_policy_filtered[provider_name]
            provider_instance_count = math.ceil(float(self.instance_count) / float(len(provider_policy_filtered)))
            if instances_created + provider_instance_count > self.instance_count:
                provider_instance_count = self.instance_count - instances_created
            instances_created += provider_instance_count

            print('creating %d instances on provider %s' % (provider_instance_count, provider_name))
            instance_type = ComputeInstanceType.objects.filter(provider=provider_name).order_by('hour_price')[0]
            if provider_instance_count > 0:
                provider = self.user_configuration.provider_configurations.get(provider_name=provider_name)
                for i in range(provider_instance_count):
                    provider_instance_ids = provider.create_instances(provider_instance_count, instance_type.external_id)
                    instance = provider_instance_models[provider_name].objects.create(external_id=provider_instance_id, provider=provider_name)
                    self.instances.add(instance)

            self.save()


class ComputeInstance(PolymorphicModel):
    external_id = models.CharField(max_length=256)
    provider_image = models.ForeignKey(ProviderImage, related_name='instances')
    group = models.ForeignKey(ComputeGroup, related_name='instances')


class Ec2ComputeInstance(ComputeInstance):
    pass


class LinodeComputeInstance(ComputeInstance):
    pass


provider_instance_models = {
    'aws': Ec2ComputeInstance,
    'linode': LinodeComputeInstance
}
