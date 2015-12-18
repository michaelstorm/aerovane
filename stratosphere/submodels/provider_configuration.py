from django.db import models, OperationalError

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeLocation
from libcloud.compute.types import NodeState

from polymorphic import PolymorphicModel

from ..models import ComputeInstance, DiskImage, OperatingSystemImage, ProviderImage, ProviderSize
from ..util import *

import json

import traceback


CLOUD_PROVIDER_DRIVERS = {}

SIMULATED_FAILURE_DRIVER = SimulatedFailureDriver()


class ProviderConfiguration(PolymorphicModel, HasLogger):
    class Meta:
        app_label = "stratosphere"

    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey('UserConfiguration', null=True, blank=True, related_name='provider_configurations')
    simulated_failure = models.BooleanField(default=False)

    default_operating_systems = {
        'Ubuntu 14.04': {
            'aws': 'ami-84bba3c1',
            'linode': '124'
        }
    }

    @property
    def driver(self):
        if self.simulated_failure:
            return SIMULATED_FAILURE_DRIVER
        else:
            if self.provider_name not in CLOUD_PROVIDER_DRIVERS:
                CLOUD_PROVIDER_DRIVERS[self.provider_name] = self.create_driver()

            return CLOUD_PROVIDER_DRIVERS[self.provider_name]

    @retry(OperationalError)
    def simulate_restore(self):
        self.logger.info('Simulating restore')
        self.simulated_failure = False
        self.save()

    @retry(OperationalError)
    def simulate_failure(self):
        self.logger.info('Simulating failure')
        self.simulated_failure = True
        self.save()

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        return self.driver.create_node(name=name, image=libcloud_image, size=libcloud_size, auth=libcloud_auth,
                                       **extra_args)

    @retry(OperationalError)
    def update_instance_statuses(self):
        instances = ComputeInstance.objects.filter(provider_image__provider_configuration=self)

        try:
            libcloud_nodes = self.driver.list_nodes()
        except Exception as e:
            print('Error listing nodes of %s' % self)

            traceback.print_exc()
            for instance in instances:
                instance.state = ComputeInstance.UNKNOWN
                instance.save()

            return

        for instance in ComputeInstance.objects.filter(provider_image__provider_configuration=self):
            nodes = list(filter(lambda node: node.id == instance.external_id, libcloud_nodes))
            self.logger.debug('%s nodes: %s' % (instance.external_id, nodes))

            if len(nodes) == 0:
                instance.state = ComputeInstance.UNKNOWN
            else:
                node = nodes[0]

                new_state = NodeState.tostring(node.state)
                if instance.state != new_state:
                    self.logger.info('Updating state of %s from %s to %s' % (instance, instance.state, new_state))
                    instance.state = new_state

                instance.private_ips = node.private_ips
                instance.public_ips = node.public_ips

            instance.save()

    def load_available_sizes(self):
        driver_sizes = self.driver.list_sizes()
        for driver_size in driver_sizes:
            if ProviderSize.objects.filter(provider_configuration=self, external_id=driver_size.id).first() is None:
                vcpus = driver_size.extra.get('vcpus')
                ProviderSize.objects.create(provider_configuration=self, external_id=driver_size.id, name=driver_size.name, price=driver_size.price,
                                            ram=driver_size.ram, disk=driver_size.disk, bandwidth=driver_size.bandwidth, vcpus=vcpus,
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
                extra_json = json.loads(json.dumps(driver_image.extra))
                provider_image = ProviderImage(provider_configuration=self, name=driver_image.name,
                                               image_id=driver_image.id, extra=extra_json)
                provider_images.append(provider_image)

        ProviderImage.objects.bulk_create(provider_images)
        print('Created %d ProviderImages' % len(provider_images))

        print('Creating Images...')
        image_count = 0
        for driver_image in filtered_driver_images: # TODO remove driver images limit
            image_name = driver_image.name if driver_image.name is not None else '<%s>' % driver_image.id
            disk_image = DiskImage.objects.filter(name=image_name).first()

            if disk_image is None:
                provider_image = self.provider_images.filter(image_id=driver_image.id).first()
                disk_image = DiskImage.objects.create(name=image_name)
                disk_image.provider_images.add(provider_image)
                image_count += 1

        for os_name in self.default_operating_systems:
            driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
            if driver_image_id is not None:
                provider_image = self.provider_images.filter(image_id=driver_image_id).first()

                os_image = OperatingSystemImage.objects.filter(name=os_name).first()
                if os_image is None:
                    os_image = OperatingSystemImage.objects.create(name=os_name)

                disk_image = provider_image.disk_image
                os_image.disk_images.add(disk_image)


class Ec2ProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

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

    def pretty_name(self):
        return 'AWS'

    def create_driver(self):
        cls = get_driver(Provider.EC2)
        return cls(self.access_key_id, self.secret_access_key, region='us-west-1')

    def get_available_sizes(self, provider_image, cpu, memory):
        sizes = self.provider_sizes.filter(vcpus__gte=cpu, ram__gte=memory)

        def filter_size(size):
            virtualization_type = provider_image.extra['virtualization_type']
            root_device_type = provider_image.extra['root_device_type']

            size_category = size.external_id.split('.')[0]
            try:
                size_combos = self.ami_requirements[size_category]['combos']
                return (virtualization_type, root_device_type) in size_combos
            except KeyError:
                return False

        return list(filter(filter_size, sizes))


class LinodeProviderConfiguration(ProviderConfiguration):
    class Meta:
        app_label = "stratosphere"

    api_key = models.CharField(max_length=128)

    def pretty_name(self):
        return 'Linode'

    def create_driver(self):
        cls = get_driver(Provider.LINODE)
        return cls(self.api_key)

    def get_available_sizes(self, provider_image, cpu, memory):
        return self.provider_sizes.filter(vcpus__gte=cpu, ram__gte=memory)

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        location = NodeLocation(id='2', name='Dallas, TX, USA', country='USA', driver=self.driver)
        return super(LinodeProviderConfiguration, self).create_libcloud_node(name=name, libcloud_image=libcloud_image,
                        libcloud_size=libcloud_size, libcloud_auth=libcloud_auth, location=location)