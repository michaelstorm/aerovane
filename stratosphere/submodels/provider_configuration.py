from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver

from libcloud.compute.types import Provider as LibcloudProvider

import libcloud.common.exceptions

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

from stratosphere.lib.provider_configuration_data_loader import ProviderConfigurationDataLoader
from stratosphere.lib.provider_configuration_status_checker import ProviderConfigurationStatusChecker

from ..models import DiskImage, ProviderImage
from ..tasks import load_provider_data
from ..util import *

import threading
import uuid


_cloud_provider_drivers = threading.local()


class CachedDriver(object):
    def __init__(self, driver, credentials):
        self.driver = driver
        self.credentials = credentials


class LibcloudDestroyError(Exception):
    pass


class ProviderConfiguration(PolymorphicModel, ProviderConfigurationStatusChecker,
                            ProviderConfigurationDataLoader,
                            HasLogger, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey('Provider', related_name='configurations')
    provider_name = models.CharField(max_length=32)
    user_configuration = models.ForeignKey('UserConfiguration', null=True, blank=True,
                                           related_name='provider_configurations')
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
