from annoying.fields import JSONField

from django.conf import settings
from django.db import models

from libcloud.compute.base import NodeImage

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

from ..util import *

import uuid


class DiskImage(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, null=True, blank=True, db_index=True)


# DiskImages can have ProviderImages from different Providers under them, so it's necessary
# to disambiguate which Provider's ProviderImage belongs to the given ComputeImage
class DiskImageMapping(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"
        unique_together = ('provider', 'disk_image', 'compute_image')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey('Provider', related_name='disk_image_mappings')
    disk_image = models.ForeignKey('DiskImage', related_name='disk_image_mappings')
    compute_image = models.ForeignKey('ComputeImage', related_name='disk_image_mappings')


class ComputeImage(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='compute_images')
    name = models.CharField(max_length=128)


# TODO convert to polymorphic class in order to implement image_is_public() from ProviderConfiguration
class ProviderImage(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # has to be nullable so we can add after bulk create
    # TODO is this still true?
    disk_image = models.ForeignKey('DiskImage', related_name='provider_images', null=True, blank=True)
    external_id = models.CharField(max_length=256, db_index=True)
    name = models.CharField(max_length=256, null=True, blank=True, db_index=True)
    extra = JSONField()

    provider = models.ForeignKey('Provider', related_name='provider_images')
    provider_configurations = models.ManyToManyField('ProviderConfiguration', related_name='provider_images')

    def to_libcloud_image(self, provider_configuration):
        return NodeImage(id=self.external_id, name=self.name, driver=provider_configuration.driver,
                         extra=self.extra)
