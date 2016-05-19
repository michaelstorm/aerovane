from django.conf import settings
from django.db import models

from save_the_change.mixins import SaveTheChange, TrackChanges

import random
import uuid


def _create_beta_key_value():
    letters = 'abcdefghjkmnpqrstwxyz'
    digits = '23456789'
    return ''.join([random.choice(letters) + random.choice(digits) for i in range(4)])


class BetaKey(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.CharField(max_length=16, default=_create_beta_key_value)
    note = models.CharField(max_length=256, default='')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='beta_keys', blank=True, null=True)

    def __str__(self):
        return 'value="%s" note="%s", user=%s' % (self.value, self.note, self.user)