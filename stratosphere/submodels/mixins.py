from django.db import models

from save_the_change.mixins import SaveTheChange, TrackChanges


# This class:
#   * only saves changed fields on objects, and
#   * creates a historical version of the object iff any field was changed
class TrackSavedChanges(SaveTheChange, TrackChanges):
    def save(self, *args, **kwargs):
        # skip_history_when_saving is an internal marker that django-simple-history uses; checking it
        # saves us from an infinite recursive loop
        if self.has_changed or hasattr(self, 'skip_history_when_saving'):
            super(TrackSavedChanges, self).save(*args, **kwargs)
        else:
            self.save_without_historical_record(*args, **kwargs)
