from django.contrib.auth.models import User
from django.db import models, OperationalError, transaction
from django.db.models import Q

from libcloud.compute.types import Provider as LibcloudProvider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeLocation
from libcloud.compute.types import NodeState

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange

from ..models import ComputeInstance, DiskImage, OperatingSystemImage, ProviderImage, ProviderSize, Provider
from ..util import *

import json
import socket
import traceback


CLOUD_PROVIDER_DRIVERS = {}

SIMULATED_FAILURE_DRIVER = SimulatedFailureDriver()


class LibcloudDestroyError(Exception):
    pass


class ProviderConfiguration(PolymorphicModel, HasLogger, SaveTheChange):
    class Meta:
        app_label = "stratosphere"

    provider = models.ForeignKey('Provider', related_name='configurations')
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey('UserConfiguration', null=True, blank=True, related_name='provider_configurations')
    simulated_failure = models.BooleanField(default=False)

    @property
    def driver(self):
        if self.simulated_failure:
            return SIMULATED_FAILURE_DRIVER
        else:
            if self.provider_name not in CLOUD_PROVIDER_DRIVERS:
                CLOUD_PROVIDER_DRIVERS[self.provider_name] = self.create_driver()

            return CLOUD_PROVIDER_DRIVERS[self.provider_name]

    @property
    def available_disk_images(self):
        return DiskImage.objects.filter(
                      Q(provider_images__provider_configuration=self)
                    | (Q(provider_images__provider_configuration=None)
                       & Q(provider_images__provider=self.provider)))

    @property
    def available_provider_images(self):
        return ProviderImage.objects.filter(
                      Q(provider_configuration=self)
                    | (Q(provider_configuration=None)
                       & Q(provider=self.provider)))

    def _destroy_all_nodes(self):
        print('listing nodes in %s' % self.provider_name)
        nodes = self.driver.list_nodes()
        print('found %d nodes in %s' % (len(nodes), self.provider_name))
        for node in nodes:
            print('destroying %s' % node.id)
            self.driver.destroy_node(node)

    # @retry(OperationalError)
    def simulate_restore(self):
        self.logger.info('Simulating restore')
        self.simulated_failure = False
        self.save()

    # @retry(OperationalError)
    def simulate_failure(self):
        self.logger.info('Simulating failure')
        with transaction.atomic():
            self.simulated_failure = True
            self.save()

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        return self.driver.create_node(name=name, image=libcloud_image, size=libcloud_size, auth=libcloud_auth,
                                       **extra_args)

    def destroy_libcloud_node(self, libcloud_node):
        if not self.driver.destroy_node(libcloud_node):
            raise LibcloudDestroyError()

    def update_instance_statuses(self):
        instances = ComputeInstance.objects.filter(provider_configuration=self)

        try:
            libcloud_nodes = self.driver.list_nodes()

        except Exception as e:
            print('Error listing nodes of %s' % self)

            traceback.print_exc()
            for instance in instances:
                instance.state = ComputeInstance.UNKNOWN
                instance.save()

        else:
            user_configurations_with_instance_state_changes = set()
            for instance in instances:
                nodes = list(filter(lambda node: node.id == instance.external_id, libcloud_nodes))

                if len(nodes) == 0:
                    # exclude ComputeInstances whose libcloud node creation jobs have not yet run
                    if instance.state != None:
                        instance.state = ComputeInstance.UNKNOWN
                else:
                    node = nodes[0]

                    instance.state = NodeState.tostring(node.state)
                    instance.private_ips = node.private_ips
                    instance.public_ips = node.public_ips

                # prevent too many history instances from being created
                if instance.has_changed:
                    if 'state' in instance.changed_fields:
                        self.logger.info('Updating state of instance %s from %s to %s' % (instance.pk, instance.old_values['state'], instance.state))

                    instance.save()
                    user_configurations_with_instance_state_changes.add(instance.group.user_configuration)

            for user_configuration in user_configurations_with_instance_state_changes:
                user_configuration.take_instance_states_snapshot()


    def load_available_sizes(self):
        driver_sizes = self.driver.list_sizes()
        for driver_size in driver_sizes:
            if ProviderSize.objects.filter(provider_configuration=self, external_id=driver_size.id).first() is None:
                vcpus = driver_size.extra.get('vcpus')
                ProviderSize.objects.create(provider_configuration=self, external_id=driver_size.id, name=driver_size.name, price=driver_size.price,
                                            ram=driver_size.ram, disk=driver_size.disk, bandwidth=driver_size.bandwidth, vcpus=vcpus,
                                            extra=json.loads(json.dumps(driver_size.extra)))

    def load_available_images(self):
        self._load_available_images()

    def _load_available_images(self, image_filter=lambda image: True):
        print('Querying images for provider %s' % self.provider_name)
        driver_images = self.driver.list_images()
        print('Retrieved %d images' % len(driver_images))

        filtered_driver_images = list(filter(image_filter, driver_images))[:100] # TODO remove driver images limit

        # for os_name in self.default_operating_systems:
        #     driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
        #     if driver_image_id is not None:
        #         if len([i for i in filtered_driver_images if i.id == driver_image_id]) == 0:
        #             filtered_driver_images.append([i for i in driver_images if i.id == driver_image_id][0])

        def driver_image_name(driver_image):
            return driver_image.name if driver_image.name is not None else '<%s>' % driver_image.id

        import time

        print('Creating DiskImages...')
        start = time.time()
        disk_images = []
        for driver_image in filtered_driver_images: # TODO remove driver images limit
            image_name = driver_image_name(driver_image)

            if not DiskImage.objects.filter(name=image_name).exists():
                disk_image = DiskImage(name=image_name)
                disk_images.append(disk_image)

        DiskImage.objects.bulk_create(disk_images)
        end = time.time()
        print('Created %d DiskImages in %d seconds' % (len(disk_images), end - start))

        print('Creating ProviderImages...')
        start = time.time()
        provider_images = []
        created = 0
        for driver_image in filtered_driver_images:
            created += 1

            if created % 100 == 0:
                print(round(float(created) / float(len(filtered_driver_images)) * 100))

            if not ProviderImage.objects.filter(image_id=driver_image.id).exists():
                image_name = driver_image_name(driver_image)
                disk_image = DiskImage.objects.filter(name=image_name).first()

                extra_json = json.loads(json.dumps(driver_image.extra))
                provider_configuration = None if extra_json.get('is_public', True) else self

                provider_image = ProviderImage(provider_configuration=provider_configuration,
                                               name=driver_image.name, image_id=driver_image.id,
                                               extra=extra_json, disk_image=disk_image,
                                               provider=self.provider)

                provider_images.append(provider_image)

        ProviderImage.objects.bulk_create(provider_images)
        end = time.time()
        print('Created %d ProviderImages in %d seconds' % (len(provider_images), end - start))

        # for os_name in self.default_operating_systems:
        #     driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
        #     if driver_image_id is not None:
        #         provider_image = self.provider_images.filter(image_id=driver_image_id).first()

        #         os_image = OperatingSystemImage.objects.filter(name=os_name).first()
        #         if os_image is None:
        #             os_image = OperatingSystemImage.objects.create(name=os_name)

        #         disk_image = provider_image.disk_image
        #         os_image.disk_images.add(disk_image)


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
                icon_path='/static/stratosphere/aws_icon.png')

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

    def load_available_images(self):
        self._load_available_images(image_filter=lambda image: image.id.startswith('ami-'))


class LinodeProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

    api_key = models.CharField(max_length=128)

    def create_driver(self):
        cls = get_driver(LibcloudProvider.LINODE)
        return cls(self.api_key)

    def get_available_sizes(self, provider_image, cpu, memory):
        return self.provider_sizes.filter(vcpus__gte=cpu, ram__gte=memory)

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        location = NodeLocation(id='2', name='Dallas, TX, USA', country='USA', driver=self.driver)
        return super(LinodeProviderConfiguration, self).create_libcloud_node(name=name, libcloud_image=libcloud_image,
                        libcloud_size=libcloud_size, libcloud_auth=libcloud_auth, location=location)