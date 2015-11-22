from annoying.fields import JSONField

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeImage, NodeSize

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
    disk_image = models.ForeignKey(DiskImage, null=True, blank=True, related_name='provider_images') # has to be nullable so we can add after bulk create
    image_id = models.CharField(max_length=256)
    name = models.CharField(max_length=256)
    extra = JSONField()

    def to_libcloud_image(self):
        return NodeImage(id=self.image_id, name=self.name, driver=self.provider_configuration.driver, extra=self.extra)


class ProviderSize(models.Model):
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_sizes')
    external_id = models.CharField(max_length=256)
    name = models.CharField(max_length=256)
    price = models.FloatField()
    ram = models.IntegerField()
    disk = models.IntegerField()
    bandwidth = models.IntegerField(null=True, blank=True)
    extra = JSONField()

    def __str__(self):
        return '%s: %s (%s)' % (self.provider_configuration.provider_name, self.name, self.external_id)

    def to_libcloud_size(self):
        return NodeSize(id=self.external_id, name=self.name, ram=self.ram, disk=self.disk, bandwidth=self.bandwidth, price=self.price,
                        driver=self.provider_configuration.driver, extra=self.extra)


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
            provider_image = self.provider_images.filter(image_id=driver_image.id).first()

            if provider_image is None:
                provider_images.append(ProviderImage(provider_configuration=self, image_id=driver_image.id,
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

                provider_image = self.provider_images.filter(image_id=driver_image.id).first()
                disk_image.provider_images.add(provider_image)

        for os_name in self.default_operating_systems:
            print('os_name:', os_name)
            driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
            if driver_image_id is not None:
                provider_image = self.provider_images.filter(image_id=driver_image_id).first()
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

    ami_requirements = {
        't1': {
            'combos': [('hvm', 'ebs'), ('paravirtual', 'ebs')],
            '32-bit_available': ['micro'],
            'current_generation': False,
        },
        't2': {
            'combos': [('hvm', 'ebs')],
            '32-bit_available': ['micro', 'small'],
            'current_generation': True,
        },
        'm4': {
            'combos': [('hvm', 'ebs')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'm3': {
            'combos': [('hvm', 'ebs'), ('hvm', 'instance-store'), ('paravirtual', 'ebs'), ('paravirtual', 'instance-store')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'm2': {
            'combos': [('paravirtual', 'ebs'), ('paravirtual', 'instance-store')],
            '32-bit_available': [],
            'current_generation': False,
        },
        'm1': {
            'combos': [('paravirtual', 'ebs'), ('paravirtual', 'instance-store')],
            '32-bit_available': [],
            'current_generation': False,
        },
        'c4': {
            'combos': [('hvm', 'ebs')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'c3': {
            'combos': [('hvm', 'ebs'), ('hvm', 'instance-store'), ('paravirtual', 'ebs'), ('paravirtual', 'instance-store')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'r3': {
            'combos': [('hvm', 'ebs'), ('hvm', 'instance-store')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'g2': {
            'combos': [('hvm', 'ebs')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'i2': {
            'combos': [('hvm', 'ebs'), ('hvm', 'instance-store')],
            '32-bit_available': [],
            'current_generation': True,
        },
        'd2': {
            'combos': [('hvm', 'ebs'), ('hvm', 'instance-store')],
            '32-bit_available': [],
            'current_generation': False,
        },
    }

    def create_driver(self):
        cls = get_driver(Provider.EC2)
        return cls(self.access_key_id, self.secret_access_key, region='us-west-1')

    def create_external_instances(self, instance_count, provider_image, cpu, memory):
        external_ids = []
        for i in range(instance_count):
            libcloud_node = self.driver.create_node(image=provider_image.to_libcloud_image(), size=size.to_libcloud_size())
            external_ids.append(libcloud_node.id)

        return external_ids


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
            provider_instances = self.instances.filter(provider_image__provider_configuration__provider_name=provider_name)
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
            if provider_instance_count > 0:
                provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)
                size = provider_configuration.provider_sizes.order_by('price')[0]
                provider_image = ProviderImage.objects.get(disk_image__operating_system_images=self.image)
                for i in range(provider_instance_count):
                    libcloud_node = provider_configuration.driver.create_node(image=provider_image.to_libcloud_image(), size=size.to_libcloud_size())
                    ComputeInstance.objects.create(external_id=libcloud_node.id, provider_image=provider_image, group=self)

            self.save()


class ComputeInstance(models.Model):
    external_id = models.CharField(max_length=256)
    provider_image = models.ForeignKey(ProviderImage, related_name='instances')
    group = models.ForeignKey(ComputeGroup, related_name='instances')
