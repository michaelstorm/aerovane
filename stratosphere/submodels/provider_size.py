from annoying.fields import JSONField

from django.db import models

from libcloud.compute.base import NodeSize

from save_the_change.mixins import SaveTheChange, TrackChanges

import uuid

from ..util import *


class ProviderSize(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='provider_sizes')
    external_id = models.CharField(max_length=256)
    name = models.CharField(max_length=256)
    price = models.FloatField()
    ram = models.IntegerField()
    disk = models.IntegerField()
    bandwidth = models.IntegerField(null=True, blank=True)
    cpu = models.IntegerField()
    extra = JSONField()

    def __str__(self):
        return '%s: %s (%s)' % (self.provider_configuration.provider_name, self.name, self.external_id)

    def to_libcloud_size(self):
        return NodeSize(id=self.external_id, name=self.name, ram=self.ram, disk=self.disk,
                        bandwidth=self.bandwidth, price=self.price,
                        driver=self.provider_configuration.driver, extra=self.extra)