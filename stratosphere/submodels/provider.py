from django.db import models


class Provider(models.Model):
    class Meta:
        app_label = "stratosphere"

    name = models.CharField(max_length=32)
    pretty_name = models.CharField(max_length=32)
    icon_path = models.CharField(max_length=128)