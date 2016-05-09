from django.contrib.sites.models import Site
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import models

from save_the_change.mixins import SaveTheChange, TrackChanges

import uuid


class Provider(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=32)
    pretty_name = models.CharField(max_length=32)
    icon_path = models.TextField()

    def icon_url(self):
        icon_path = staticfiles_storage.url(self.icon_path)
        current_site = Site.objects.get_current()
        return '//' + current_site.domain + icon_path

    def __repr__(self):
        return '<Provider %s: %s>' % (self.name, self.pk)