from django.db import models

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange, TrackChanges

import uuid


class ProviderCredentialSet(PolymorphicModel, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    UNAUTHORIZED_CREDENTIALS = 'UNAUTHORIZED_CREDENTIALS'
    UNKNOWN_ERROR = 'UNKNOWN_ERROR'

    ERROR_TYPE_CHOICES = (
        (INVALID_CREDENTIALS, 'INVALID_CREDENTIALS'),
        (UNAUTHORIZED_CREDENTIALS, 'UNAUTHORIZED_CREDENTIALS'),
        (UNKNOWN_ERROR, 'UNKNOWN_ERROR'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    error_type = models.CharField(max_length=24, null=True, blank=True, choices=ERROR_TYPE_CHOICES)
