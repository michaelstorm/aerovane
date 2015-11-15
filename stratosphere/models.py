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


class ProviderImage(models.Model):
    provider_name = models.CharField(max_length=32)
    image_id = models.CharField(max_length=128)


class Image(models.Model):
    name = models.CharField(max_length=128)
    provider_images = models.ManyToManyField(ProviderImage)


class OperatingSystem(models.Model):
    name = models.CharField(max_length=128)
    images = models.ManyToManyField(Image)


class ProviderConfiguration(PolymorphicModel):
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey(UserConfiguration, null=True, blank=True, related_name='provider_configurations')

    @property
    def driver(self):
        if self.provider_name not in CLOUD_PROVIDER_DRIVERS:
            CLOUD_PROVIDER_DRIVERS[self.provider_name] = self.create_driver()

        return CLOUD_PROVIDER_DRIVERS[self.provider_name]

    def load_available_images(self):
        driver_images = self.driver.list_images()

        # TODO remove driver images limit
        for driver_image in driver_images[:1000]:
            print('Adding image id: "%s", name: "%s"' % (driver_image.id, driver_image.name))

            provider_image = ProviderImage.objects.filter(provider_name=self.provider_name, image_id=driver_image.id).first()

            if provider_image is None:
                provider_image = ProviderImage.objects.create(provider_name=self.provider_name, image_id=driver_image.id)

                image_name = driver_image.name if driver_image.name is not None else '<%s>' % driver_image.id
                image = Image.objects.filter(name=image_name).first()

                if image is None:
                    image = Image.objects.create(name=image_name)
                    image.provider_images.add(provider_image)


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
        configuration = UserConfiguration(user=instance)
        configuration.save()


class ComputeInstanceType(PolymorphicModel):
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    name = models.CharField(max_length=32)
    cpu = models.IntegerField()
    memory = models.IntegerField()
    attached_storage = models.IntegerField()
    hour_price = models.IntegerField()
    external_id = models.CharField(max_length=32)

    def __str__(self):
        return '%s %s' % (self.get_provider_display(), self.name)


class ComputeGroup(PolymorphicModel):
    instance_count = models.IntegerField()
    cpu = models.IntegerField()
    memory = models.IntegerField()
    name = models.CharField(max_length=128)
    provider_policy = models.TextField()

    def _provider_policy_filtered(self):
        provider_policy_deserialized = json.loads(self.provider_policy)
        return {provider_name: provider_policy_deserialized[provider_name] for provider_name in provider_policy_deserialized
                if provider_name in settings.CLOUD_PROVIDERS}

    def provider_states(self):
        provider_policy_filtered = self._provider_policy_filtered()
        provider_states_map = {}

        for provider_name in provider_policy_filtered:
            provider_instances = self.instances.filter(provider=provider_name)
            if len(provider_instances) > 0:
                provider_states_map[provider_instances[0].provider] = len(provider_instances)

        return provider_states_map

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
                provider_instance_ids = settings.CLOUD_PROVIDERS[provider_name].create_instances(provider_instance_count, instance_type.external_id)
                for provider_instance_id in provider_instance_ids:
                    instance = provider_instance_models[provider_name].objects.create(external_id=provider_instance_id, provider=provider_name)
                    self.instances.add(instance)

            self.save()


class ImageComputeGroup(ComputeGroup):
    image_id = models.CharField(max_length=64)


class OsComputeGroup(ComputeGroup):
    os = models.CharField(max_length=64)


class ComputeInstance(PolymorphicModel):
    external_id = models.CharField(max_length=256)
    provider = models.CharField(max_length=256, choices=PROVIDER_CHOICES)
    group = models.ForeignKey(ComputeGroup, blank=True, null=True, related_name='instances')


class Ec2ComputeInstance(ComputeInstance):
    pass


class LinodeComputeInstance(ComputeInstance):
    pass


provider_instance_models = {
    'aws': Ec2ComputeInstance,
    'linode': LinodeComputeInstance
}
