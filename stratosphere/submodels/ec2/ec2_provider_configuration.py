from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

from stratosphere.models import ProviderConfiguration, Provider
from stratosphere.tasks import load_provider_data
from stratosphere.util import schedule_random_default_delay

import uuid


class Ec2ProviderCredentials(models.Model):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access_key_id = models.CharField(max_length=128)
    secret_access_key = models.CharField(max_length=128)


class Ec2ProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

    region = models.CharField(max_length=16)
    credentials = models.ForeignKey('Ec2ProviderCredentials', related_name='configurations')

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

    regions = {
       'us-east-1': 'US East (N. Virginia)',
       'us-west-1': 'US West (N. California)',
       'us-west-2': 'US West (Oregon)',
    }

    @staticmethod
    def _provider_name_from_region(region):
        return 'aws_%s' % region.replace('-', '_')

    @staticmethod
    def create_providers():
        for region, pretty_name in Ec2ProviderConfiguration.regions.items():
            provider_name = Ec2ProviderConfiguration._provider_name_from_region(region)
            provider = Provider.objects.create(
                name=provider_name,
                pretty_name='AWS %s' % pretty_name,
                icon_path='stratosphere/aws_icon.png')

    @staticmethod
    def create_regions(user_configuration, access_key_id, secret_access_key):
        credentials = Ec2ProviderCredentials.objects.create(
                            access_key_id=access_key_id, secret_access_key=secret_access_key)

        for region, pretty_name in Ec2ProviderConfiguration.regions.items():
            provider_name = Ec2ProviderConfiguration._provider_name_from_region(region)
            provider = Provider.objects.get(name=provider_name)

            Ec2ProviderConfiguration.objects.create(
                provider=provider,
                provider_name=provider_name,
                region=region,
                credentials=credentials,
                user_configuration=user_configuration)

    def create_driver(self):
        cls = get_driver(LibcloudProvider.EC2)
        return cls(self.credentials.access_key_id, self.credentials.secret_access_key,
                   region=self.region)

    def get_available_sizes(self, provider_image, cpu, memory):
        sizes = self.provider_sizes.filter(cpu__gte=cpu, ram__gte=memory)

        def filter_size(provider_size):
            virtualization_type = provider_image.extra['virtualization_type']
            root_device_type = provider_image.extra['root_device_type']

            size_category = provider_size.external_id.split('.')[0]
            try:
                size_combos = self.ami_requirements[size_category]['combos']
                return (virtualization_type, root_device_type) in size_combos
            except KeyError:
                return False

        return list(filter(filter_size, sizes))

    def _get_credentials_dict(self):
        return {'access_key_id': self.credentials.access_key_id,
                'secret_access_key': self.credentials.secret_access_key}

    def _get_driver_images(self, include_public):
        filters = {'image-type': 'machine', 'state': 'available'}
        if not include_public:
            filters['is-public'] = False

        return self.driver.list_images(ex_filters=filters)

    def admin_url(self, compute_instance=None):
        base_url = "https://console.aws.amazon.com/ec2/home?region=%s" % self.region
        if compute_instance is None:
            return base_url
        else:
            return "#Instances%s:search=%s" % (base_url, compute_instance.external_id)


@receiver(post_save, sender=Ec2ProviderCredentials)
def schedule_load_provider_info_credentials(sender, created, instance, **kwargs):
    # TODO is this method called before or after the relation is created?
    for provider_configuration in instance.configurations.all():
        schedule_random_default_delay(load_provider_data, provider_configuration.pk)