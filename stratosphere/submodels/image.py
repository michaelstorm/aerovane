from annoying.fields import JSONField

from django.contrib.auth.models import User
from django.db import models

from libcloud.compute.base import NodeImage

from save_the_change.mixins import SaveTheChange

from ..util import *


class DiskImage(models.Model, SaveTheChange):
    class Meta:
        app_label = "stratosphere"

    name = models.CharField(max_length=128, db_index=True)


class DiskImageMapping(models.Model, SaveTheChange):
    class Meta:
        app_label = "stratosphere"
        unique_together = ('provider', 'disk_image', 'operating_system_image')

    provider = models.ForeignKey('Provider')
    disk_image = models.ForeignKey('DiskImage', related_name='disk_image_mappings')
    operating_system_image = models.ForeignKey('OperatingSystemImage', related_name='disk_image_mappings')


class OperatingSystemImage(models.Model, SaveTheChange):
    class Meta:
        app_label = "stratosphere"

    user = models.ForeignKey(User)
    name = models.CharField(max_length=128)


class ProviderImage(models.Model, SaveTheChange):
    class Meta:
        app_label = "stratosphere"

    # has to be nullable so we can add after bulk create
    disk_image = models.ForeignKey('DiskImage', related_name='provider_images', null=True, blank=True)
    image_id = models.CharField(max_length=256, db_index=True)
    name = models.CharField(max_length=256, null=True, blank=True, db_index=True)
    extra = JSONField()

    provider = models.ForeignKey('Provider', related_name='provider_images')

    # TODO make this a many-to-many relation to support shared private images
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_images',
                                               null=True, blank=True)

    def to_libcloud_image(self, provider_configuration):
        return NodeImage(id=self.image_id, name=self.name, driver=provider_configuration.driver,
                         extra=self.extra)