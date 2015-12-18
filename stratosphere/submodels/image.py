from annoying.fields import JSONField

from django.db import models

from libcloud.compute.base import NodeImage

from ..util import *


class DiskImage(models.Model):
    class Meta:
        app_label = "stratosphere"

    name = models.CharField(max_length=128, db_index=True)


class OperatingSystemImage(models.Model):
    class Meta:
        app_label = "stratosphere"

    name = models.CharField(max_length=128)
    disk_images = models.ManyToManyField('DiskImage', related_name='operating_system_images')


class ProviderImage(models.Model):
    class Meta:
        app_label = "stratosphere"

    # has to be nullable so we can add after bulk create
    disk_image = models.ForeignKey('DiskImage', related_name='provider_images', null=True, blank=True)
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_images')
    image_id = models.CharField(max_length=256, db_index=True)
    name = models.CharField(max_length=256, null=True, blank=True, db_index=True)
    extra = JSONField()

    def to_libcloud_image(self):
        return NodeImage(id=self.image_id, name=self.name, driver=self.provider_configuration.driver,
                         extra=self.extra)