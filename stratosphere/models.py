from django.conf import settings
from django.db import models

import json
import math

from polymorphic import PolymorphicModel


PROVIDER_CHOICES = (
    ('aws', 'Amazon Web Services'),
    ('azure', 'Microsoft Azure'),
    ('linode', 'Linode'),
    ('digitalocean', 'DigitalOcean'),
    ('softlayer', 'SoftLayer'),
    ('cloudsigma', 'CloudSigma'),
    ('google', 'Google App Engine'),
)


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
