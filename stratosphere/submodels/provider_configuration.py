from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models, OperationalError, transaction
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from libcloud.compute.types import Provider as LibcloudProvider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeLocation
from libcloud.compute.types import NodeState

import libcloud.common.exceptions

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..models import ComputeInstance, DiskImage, OperatingSystemImage, ProviderImage, ProviderSize, Provider
from ..tasks import load_provider_data
from ..util import *

import json
import socket
import threading
import traceback
import uuid


_cloud_provider_drivers = threading.local()


class CachedDriver(object):
    def __init__(self, driver, credentials):
        self.driver = driver
        self.credentials = credentials


class LibcloudDestroyError(Exception):
    pass


class ProviderConfiguration(PolymorphicModel, HasLogger, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    provider = models.ForeignKey('Provider', related_name='configurations')
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey('UserConfiguration', null=True, blank=True, related_name='provider_configurations')
    loaded = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)

    @property
    def driver(self):
        driver_attr = 'driver_%d' % self.pk
        credentials = self._get_credentials_dict()
        create_new_driver = False

        if not hasattr(_cloud_provider_drivers, driver_attr):
            create_new_driver = True
        else:
            existing_cached_driver = getattr(_cloud_provider_drivers, driver_attr)
            if existing_cached_driver.credentials != credentials:
                create_new_driver = True

        if create_new_driver:
            cached_driver = CachedDriver(self.create_driver(), credentials)
            setattr(_cloud_provider_drivers, driver_attr, cached_driver)

        return getattr(_cloud_provider_drivers, driver_attr).driver

    @property
    def available_disk_images(self):
        return DiskImage.objects.filter(
                      Q(provider_images__provider_configurations=self)
                    | (Q(provider_images__provider_configurations=None)
                       & Q(provider_images__provider=self.provider)))

    @property
    def available_provider_images(self):
        return ProviderImage.objects.filter(
                      Q(provider_configurations=self)
                    | (Q(provider_configurations=None)
                       & Q(provider=self.provider)))

    def _destroy_all_nodes(self):
        print('listing nodes in %s' % self.provider_name)
        nodes = self.driver.list_nodes()
        print('found %d nodes in %s' % (len(nodes), self.provider_name))
        for node in nodes:
            print('destroying %s' % node.id)
            try:
                self.driver.destroy_node(node)
            except Exception as e:
                print(e)

    def create_libcloud_node(self, name, libcloud_image, libcloud_size, libcloud_auth, **extra_args):
        return self.driver.create_node(name=name, image=libcloud_image, size=libcloud_size, auth=libcloud_auth,
                                       **extra_args)

    def destroy_libcloud_node(self, libcloud_node):
        try:
            if not self.driver.destroy_node(libcloud_node):
                raise LibcloudDestroyError()
        except libcloud.common.exceptions.BaseHTTPError as e:
            if 'InvalidInstanceID.NotFound' in e.message:
                self.logger.warning('Instance %s already destroyed (%s)' % (libcloud_node.id, e.message))
            else:
                raise e

    def set_enabled(self, enabled):
        with transaction.atomic():
            if enabled:
                now = timezone.now()
                terminated_instances = self.instances.filter(~Q(failed_at=None))
                for instance in terminated_instances:
                    instance.failure_ignored = True
                    instance.save()

                self.enabled = True
                self.save()

            else:
                self.enabled = False
                self.save()

    @thread_local(DB_OVERRIDE='serializable')
    def check_enabled(self):
        instance_count = self.instances.count()
        max_failure_count = instance_count if instance_count < 3 else 3

        now = timezone.now()
        one_hour_ago = now - timedelta(hours=1)
        failure_count = self.instances.filter(failed_at__gt=one_hour_ago, failure_ignored=False).count()

        self.logger.info('Instance count: %d, max failure count: %d, failure count: %d' %
                         (instance_count, max_failure_count, failure_count))

        if self.enabled:
            if max_failure_count > 0 and failure_count >= max_failure_count:
                self.logger.warn('Disabling provider %d (%s)' % (self.pk, self.provider.name))
                self.enabled = False
                self.save()
        else:
            self.logger.info('Provider %d (%s) already disabled' % (self.pk, self.provider.name))

    def check_failed_instances(self):
        now = timezone.now()
        query = ComputeInstance.terminated_instances_query(now) & Q(failed_at=None)
        terminated_not_failed_instances = self.instances.filter(query)

        self.logger.info('Found %d terminated instances that are not yet failed for provider %d' % (terminated_not_failed_instances.count(), self.provider.pk))

        for instance in terminated_not_failed_instances:
            self.logger.warn('Marking instance %d failed' % instance.pk)
            instance.failed_at = now
            instance.save()

    def update_instance_statuses(self):
        try:
            libcloud_nodes = self.driver.list_nodes()

        except Exception as e:
            print('Error listing nodes of %s' % self)

            traceback.print_exc()
            for instance in self.instances.all():
                instance.state = ComputeInstance.UNKNOWN
                instance.save()

        else:
            # exclude ComputeInstances whose libcloud node creation jobs have not yet run
            for instance in self.instances.filter(~Q(external_id=None)):
                nodes = list(filter(lambda node: node.id == instance.external_id, libcloud_nodes))

                previous_state = instance.state

                if len(nodes) == 0:
                    instance.state = ComputeInstance.TERMINATED
                else:
                    node = nodes[0]

                    self.logger.warn('Remote node %s state: %s' % (instance.pk, NodeState.tostring(node.state)))

                    instance.state = NodeState.tostring(node.state)
                    instance.private_ips = node.private_ips
                    instance.public_ips = node.public_ips

                # prevent too many history instances from being created
                if instance.has_changed:
                    if 'state' in instance.changed_fields:
                        self.logger.info('Updating state of instance %s from %s to %s' % (instance.pk, instance.old_values['state'], instance.state))

                    instance.save()

            with thread_local(DB_OVERRIDE='serializable'):
                self.user_configuration.take_instance_states_snapshot_if_changed()

    def _load_available_sizes(self):
        driver_sizes = self.driver.list_sizes()
        provider_size_ids = set(self.provider_sizes.values_list('id', flat=True))

        for driver_size in driver_sizes:
            provider_size = ProviderSize.objects.filter(external_id=driver_size.id, provider_configuration=self).first()
            if provider_size is None:
                provider_size = ProviderSize(external_id=driver_size.id, provider_configuration=self)
            else:
                provider_size_ids.remove(provider_size.pk)

            provider_size.name = driver_size.name
            provider_size.price = driver_size.price
            provider_size.ram = driver_size.ram
            provider_size.disk = driver_size.disk
            provider_size.vcpus = driver_size.extra.get('vcpus')
            provider_size.bandwidth = driver_size.bandwidth
            provider_size.extra = json.loads(json.dumps(driver_size.extra))

            provider_size.save()

        # remaining elements of provider_size_ids are those elements deleted remotely
        ProviderSize.objects.filter(pk__in=provider_size_ids).delete()

    def _get_driver_images(self, include_public):
        return self.driver.list_images()

    # TODO locally delete images deleted remotely
    # TODO don't limit driver images by default
    def _load_available_images(self, include_public, driver_images_limit=1000, row_retrieval_chunk_size=100):
        def driver_image_name(driver_image):
            return driver_image.name if driver_image.name is not None else '<%s>' % driver_image.id

        def get_provider_images_by_external_id(driver_images):
            driver_images_by_id = {driver_image.id: driver_image for driver_image in driver_images}
            provider_images = ProviderImage.objects.filter(provider=self.provider,
                                                           external_id__in=driver_images_by_id.keys())
            return {provider_image.external_id: provider_image for provider_image in provider_images}

        import itertools
        def grouper(n, iterable):
            it = iter(iterable)
            while True:
               chunk = tuple(itertools.islice(it, n))
               if not chunk:
                   return
               yield chunk

        print('Querying images for provider %s' % self.provider_name)
        start = timezone.now()
        driver_images = self._get_driver_images(include_public)
        end = timezone.now()
        print('Retrieved %d images in %s' % (len(driver_images), (end - start)))

        filtered_driver_images = list(driver_images)
        if driver_images_limit is not None:
            filtered_driver_images = filtered_driver_images[:driver_images_limit]

        print('Scanning driver and updating provider images...')
        start = timezone.now()

        modified = 0
        scanned = 0
        new_driver_images_by_provider_id = {}
        for driver_images_chunk in grouper(row_retrieval_chunk_size, filtered_driver_images):
            provider_images_by_external_id = get_provider_images_by_external_id(driver_images_chunk)

            for driver_image in driver_images_chunk:
                provider_image = provider_images_by_external_id.get(driver_image.id)
                if provider_image is None:
                    new_provider_id = uuid.uuid4()
                    new_driver_images_by_provider_id[new_provider_id] = driver_image
                else:
                    provider_image.extra = json.loads(json.dumps(driver_image.extra))

                    if provider_image.has_changed:
                        modified += 1
                        provider_image.save()

            scanned += len(driver_images_chunk)
            print('%d%%' % round(float(scanned) / float(len(filtered_driver_images)) * 100))

        end = timezone.now()
        print('Scanned %d driver images and modified %d ProviderImages in %s' %
              (len(filtered_driver_images), modified, end - start))

        with transaction.atomic():
            new_driver_image_names = {driver_image: driver_image_name(driver_image)
                                      for driver_image in new_driver_images_by_provider_id.values()}

            print('Creating DiskImages...')
            start = timezone.now()

            new_disk_images_by_provider_id = {new_provider_id: DiskImage(name=new_driver_image_names[driver_image])
                                              for new_provider_id, driver_image in new_driver_images_by_provider_id.items()}
            DiskImage.objects.bulk_create(new_disk_images_by_provider_id.values())

            end = timezone.now()
            print('Created %d DiskImages in %s' % (len(new_disk_images_by_provider_id), end - start))

            print('Creating ProviderImages...')
            start = timezone.now()

            new_provider_images = [ProviderImage(id=new_provider_id,
                                                 provider=self.provider,
                                                 external_id=driver_image.id,
                                                 name=new_driver_image_names[driver_image],
                                                 extra=json.loads(json.dumps(driver_image.extra)),
                                                 disk_image=new_disk_images_by_provider_id[new_provider_id])
                                   for new_provider_id, driver_image in new_driver_images_by_provider_id.items()]
            ProviderImage.objects.bulk_create(new_provider_images)

            end = timezone.now()
            print('Created %d ProviderImages in %s' % (len(new_provider_images), end - start))

            print('Linking ProviderImages to DiskImages...')
            start = timezone.now()

            scanned = 0
            linked = 0
            new_driver_images = new_driver_images_by_provider_id.values()
            for driver_images_chunk in grouper(row_retrieval_chunk_size, new_driver_images):
                provider_images_by_external_id = get_provider_images_by_external_id(driver_images_chunk)

                for driver_image in driver_images_chunk:
                    provider_image = provider_images_by_external_id[driver_image.id]

                    # TODO this is Amazon-specific
                    if not provider_image.extra.get('is_public'):
                        linked += len(driver_images_chunk)
                        provider_image.provider_configurations.add(self)
                        provider_image.save()

                scanned += len(driver_images_chunk)
                print('%d%%' % round(float(scanned) / float(len(new_driver_images)) * 100))

            end = timezone.now()
            print('Linked %d ProviderImages to DiskImages in %s' % (linked, end - start))

    def load_data(self, include_public):
        self._load_available_sizes()
        self._load_available_images(include_public)

        self.loaded = True
        self.save()


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

    def _get_credentials_dict(self):
        return {'api_key': self.api_key}


@receiver(post_save, sender=ProviderConfiguration)
def schedule_load_provider_info(sender, created, instance, **kwargs):
    if created:
        schedule_random_default_delay(load_provider_data, instance.pk)


@receiver(post_save, sender=Ec2ProviderCredentials)
def schedule_load_provider_info_credentials(sender, created, instance, **kwargs):
    # TODO is this method called before or after the relation is created?
    for provider_configuration in instance.configurations.all():
        schedule_random_default_delay(load_provider_data, provider_configuration.pk)