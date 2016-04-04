from django.db import models

from save_the_change.mixins import SaveTheChange, TrackChanges

class Provider(models.Model, SaveTheChange, TrackChanges):
    class Meta:
        app_label = "stratosphere"

    name = models.CharField(max_length=32)
    pretty_name = models.CharField(max_length=32)
    icon_path = models.TextField()

    def __repr__(self):
        return '<Provider %s: %d>' % (self.name, self.pk)