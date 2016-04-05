from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

from stratosphere.models import ProviderConfiguration, Provider


class Ec2ProviderCredentials(models.Model):
    class Meta:
        app_label = "stratosphere"

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

    @staticmethod
    def create_regions(user, access_key_id, secret_access_key):
        credentials = Ec2ProviderCredentials.objects.create(
                            access_key_id=access_key_id, secret_access_key=secret_access_key)

        regions = {
           'us-east-1': 'US East (N. Virginia)',
           'us-west-1': 'US West (N. California)',
           'us-west-2': 'US West (Oregon)',
        }

        for region, pretty_name in regions.items():
            name = 'aws_%s' % region.replace('-', '_')
            provider = Provider.objects.create(
                name=name,
                pretty_name='AWS %s' % pretty_name,
                icon_path='stratosphere/aws_icon.png')

            Ec2ProviderConfiguration.objects.create(
                provider=provider,
                provider_name=name,
                region=region,
                credentials=credentials,
                user_configuration=user.configuration)

    def create_driver(self):
        cls = get_driver(LibcloudProvider.EC2)
        return cls(self.credentials.access_key_id, self.credentials.secret_access_key,
                   region=self.region)

    def get_available_sizes(self, provider_image, cpu, memory):
        sizes = self.provider_sizes.filter(vcpus__gte=cpu, ram__gte=memory)

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


@receiver(post_save, sender=Ec2ProviderCredentials)
def schedule_load_provider_info_credentials(sender, created, instance, **kwargs):
    # TODO is this method called before or after the relation is created?
    for provider_configuration in instance.configurations.all():
        schedule_random_default_delay(load_provider_data, provider_configuration.pk)