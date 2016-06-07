from django.conf import settings
from django.db import models

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

import uuid


class Event(PolymorphicModel):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='events')
    provider_configuration = models.ForeignKey('ProviderConfiguration', related_name='events', null=True, blank=True)
    compute_group = models.ForeignKey('ComputeGroup', related_name='events', null=True, blank=True)
    compute_instance = models.ForeignKey('ComputeInstance', related_name='events', null=True, blank=True)
