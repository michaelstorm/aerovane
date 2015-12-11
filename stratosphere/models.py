from annoying.fields import JSONField

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models, transaction, OperationalError
from django.db.models.signals import post_save
from django.dispatch import receiver

import hashlib

from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import Node, NodeImage, NodeSize, NodeAuthPassword, NodeAuthSSHKey, NodeLocation
from libcloud.compute.types import NodeState

import logging

from multicloud.celery import app

from polymorphic import PolymorphicModel

from .util import *

import json
import math

import traceback


CLOUD_PROVIDER_DRIVERS = {}

SIMULATED_FAILURE_DRIVER = SimulatedFailureDriver()


class HasLogger(object):
    _logger = None

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)

        return self._logger


class UserConfiguration(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='configuration')

    def avatar_url(self):
        return 'http://www.gravatar.com/avatar/%s?s=48' % hashlib.md5(self.user.email.strip().lower().encode('utf-8')).hexdigest() 


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_configuration_for_new_user(sender, created, instance, **kwargs):
    if created:
        UserConfiguration.objects.create(user=instance)


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
    vcpus = models.IntegerField(null=True, blank=True)
    extra = JSONField()

    def __str__(self):
        return '%s: %s (%s)' % (self.provider_configuration.provider_name, self.name, self.external_id)

    def to_libcloud_size(self):
        return NodeSize(id=self.external_id, name=self.name, ram=self.ram, disk=self.disk, bandwidth=self.bandwidth, price=self.price,
                        driver=self.provider_configuration.driver, extra=self.extra)


class ProviderConfiguration(PolymorphicModel, HasLogger):
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey(UserConfiguration, null=True, blank=True, related_name='provider_configurations')
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
            driver_image_id = self.default_operating_systems[os_name].get(self.provider_name)
            if driver_image_id is not None:
                provider_image = self.provider_images.filter(image_id=driver_image_id).first()

                os_image = OperatingSystemImage.objects.filter(name=os_name).first()
                if os_image is None:
                    os_image = OperatingSystemImage.objects.create(name=os_name)

                disk_image = provider_image.disk_image
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


class AuthenticationMethod(PolymorphicModel):
    user_configuration = models.ForeignKey(UserConfiguration, related_name='authentication_methods')
    name = models.CharField(max_length=64)


class PasswordAuthenticationMethod(AuthenticationMethod):
    password = models.CharField(max_length=256)

    def pretty_type(self):
        return 'Password'


class KeyAuthenticationMethod(AuthenticationMethod):
    key = models.TextField()

    def pretty_type(self):
        return 'Key'


class ComputeGroup(PolymorphicModel, HasLogger):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    TERMINATED = 'TERMINATED'

    STATE_CHOICES = (
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (STOPPED, 'Stopped'),
        (TERMINATED, 'Terminated'),
    )

    user_configuration = models.ForeignKey(UserConfiguration, related_name='compute_groups')
    instance_count = models.IntegerField()
    cpu = models.IntegerField()
    memory = models.IntegerField()
    name = models.CharField(max_length=128)
    provider_policy = models.TextField()
    updating_distribution = models.BooleanField(default=False)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    authentication_method = models.ForeignKey(AuthenticationMethod, related_name='compute_groups')

    def _provider_policy_filtered(self):
        provider_policy_deserialized = json.loads(self.provider_policy)
        return provider_policy_deserialized

    def provider_states(self):
        provider_policy_filtered = self._provider_policy_filtered()
        provider_states_map = {}

        for provider_name in provider_policy_filtered:
            provider_configuration = ProviderConfiguration.objects.filter(provider_name=provider_name).first()
            provider_instances = self.instances.filter(provider_image__provider_configuration__provider_name=provider_name)
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (ComputeInstance.PENDING, ComputeInstance.REBOOTING), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING),
                                               provider_instances)))

            provider_states_map[provider_name] = {
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.pretty_name(),
            }

        return provider_states_map

    def check_instance_distribution(self):
        try:
            with transaction.atomic():
                if self.updating_distribution:
                    return
                else:
                    self.updating_distribution = True
                    self.save()

        except OperationalError as e:
            print('OperationalError', e)
            return

        try:
            self.logger.debug('%s state: %s' % (self.name, self.state))

            instances_flat = list(self.instances.all())
            created_count = len(instances_flat)
            unknown_count = len(list(filter(lambda i: i.state not in (ComputeInstance.PENDING, ComputeInstance.RUNNING), instances_flat)))
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
            non_pending_count = len(list(filter(lambda i: i.state != ComputeInstance.PENDING, instances_flat)))
            non_terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.TERMINATED, ComputeInstance.UNKNOWN), instances_flat)))
            non_running_instances = list(filter(lambda i: i.state != ComputeInstance.RUNNING, instances_flat))

            if self.state == self.TERMINATED:
                self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
                if non_terminated_count == 0:
                    self.logger.info('Deleting self.')
                    print(self.delete())
            else:
                if self.state == self.PENDING and non_pending_count >= self.instance_count:
                    self.state = self.RUNNING

                self.logger.debug('created_count >= self.instance_count: %d >= %d: %s'
                                  % (created_count, self.instance_count, created_count >= self.instance_count))

                self.logger.debug('created_count - unknown_count < self.instance_count: %d - %d < %d: %s'
                                  % (created_count, unknown_count, self.instance_count, created_count - unknown_count < self.instance_count))

                if created_count >= self.instance_count and created_count - unknown_count < self.instance_count:
                    bad_provider_ids = set([instance.provider_image.provider_configuration.pk for instance in self.instances.all()])
                    good_provider_ids = [provider.pk for provider in ProviderConfiguration.objects.exclude(pk__in=bad_provider_ids)]

                    new_size = self._get_best_size(good_provider_ids)
                    self._create_compute_instances(new_size)

                if running_count >= self.instance_count:
                    for instance in non_running_instances:
                        self._destroy_instance(instance)

        finally:
            saved = False

            while not saved:
                try:
                    # don't re-save if deleted earlier
                    if ComputeGroup.objects.filter(pk=self.pk).exists():
                        self.updating_distribution = False
                        self.save()

                    saved = True

                except OperationalError:
                    pass

    def _create_compute_instance_entry(self, provider_image, provider_size, libcloud_node):
        return ComputeInstance.objects.create(external_id=libcloud_node.id, provider_image=provider_image, group=self, name=libcloud_node.name,
                                              state=NodeState.tostring(libcloud_node.state), public_ips=json.loads(json.dumps(libcloud_node.public_ips)),
                                              private_ips=json.loads(json.dumps(libcloud_node.private_ips)), size=provider_size,
                                              extra=json.loads(json.dumps(libcloud_node.extra, cls=NodeJSONEncoder)))

    def _destroy_instance(self, instance):
        pass

    def create_instances(self):
        selected_size = self._get_best_size()
        self._create_compute_instances(selected_size)

    def terminate(self):
        self.state = self.TERMINATED
        self.save()

        for instance in self.instances.all():
            try:
                instance.provider_image.provider_configuration.driver.destroy_node(instance.to_libcloud_node())
            except Exception:
                traceback.print_exc()



class ImageComputeGroup(ComputeGroup):
    image = models.ForeignKey(DiskImage, related_name='compute_groups')


class OperatingSystemComputeGroup(ComputeGroup):
    image = models.ForeignKey(OperatingSystemImage, related_name='compute_groups')

    def _get_best_size(self, allowed_provider_ids=None):
        provider_policy_filtered = self._provider_policy_filtered()

        available_sizes = []
        print('provider_policy_filtered:', provider_policy_filtered)
        for provider_name in provider_policy_filtered:
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            print('allowed_provider_ids:', allowed_provider_ids, 'provider_configuration.pk:', provider_configuration.pk)
            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                provider_image = provider_configuration.provider_images.get(disk_image__operating_system_images=self.image)
                available_sizes.extend(provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory))

        available_sizes.sort(key=lambda s: s.price)
        return available_sizes[0]

    def _create_compute_instances(self, selected_size):
        provider_configuration = selected_size.provider_configuration
        provider_image = provider_configuration.provider_images.get(disk_image__operating_system_images=self.image)

        for i in range(self.instance_count):
            if isinstance(self.authentication_method, PasswordAuthenticationMethod):
                libcloud_auth = NodeAuthPassword(self.authentication_method.password)
            else:
                libcloud_auth = NodeAuthSSHKey(self.authentication_method.key)

            libcloud_node = provider_configuration.create_libcloud_node(name='%s-%d' % (self.name, i), libcloud_image=provider_image.to_libcloud_image(),
                                                                        libcloud_size=selected_size.to_libcloud_size(), libcloud_auth=libcloud_auth)
            self._create_compute_instance_entry(provider_image, selected_size, libcloud_node)


class ComputeInstance(models.Model):
    RUNNING = 'RUNNING'
    REBOOTING = 'REBOOTING'
    TERMINATED = 'TERMINATED'
    PENDING = 'PENDING'
    STOPPED = 'STOPPED'
    SUSPENDED = 'SUSPENDED'
    PAUSED = 'PAUSED'
    ERROR = 'ERROR'
    UNKNOWN = 'UNKNOWN'

    STATE_CHOICES = (
        (RUNNING, 'Running'),
        (REBOOTING, 'Rebooting'),
        (TERMINATED, 'Terminated'),
        (PENDING, 'Pending'),
        (STOPPED, 'Stopped'),
        (SUSPENDED, 'Suspended'),
        (PAUSED, 'Paused'),
        (ERROR, 'Error'),
        (UNKNOWN, 'Unknown'),
    )

    external_id = models.CharField(max_length=256)
    provider_image = models.ForeignKey(ProviderImage, related_name='instances')
    group = models.ForeignKey(ComputeGroup, related_name='instances')
    name = models.CharField(max_length=256)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=UNKNOWN)
    public_ips = JSONField()
    private_ips = JSONField()
    size = models.ForeignKey(ProviderSize, related_name='instances')
    extra = JSONField()

    def to_libcloud_node(self):
        return Node(id=self.external_id, name=self.name, state=NodeState.fromstring(self.state), public_ips=self.public_ips,
                    private_ips=self.private_ips, driver=self.provider_image.provider_configuration.driver, size=self.size.to_libcloud_size(),
                    image=self.provider_image.to_libcloud_image(), extra=decode_node_extra(self.extra))


@receiver(post_save, sender=ComputeInstance)
def check_instance_distribution(sender, created, instance, **kwargs):
    compute_group = instance.group
    if not compute_group.updating_distribution:
        compute_group.check_instance_distribution()
