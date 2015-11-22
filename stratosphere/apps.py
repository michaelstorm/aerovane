from django.apps import AppConfig
from django.db.models.signals import post_save

from .models import ComputeGroup


def create_instances_signal_handler(sender, **kwargs):
    pass
    # if kwargs['created']:
    #     kwargs['instance'].create_instances()


class StratosphereConfig(AppConfig):
    name = 'stratosphere'
    verbose_name = "Stratosphere"

    def ready(self):
        post_save.connect(create_instances_signal_handler, sender=ComputeGroup, dispatch_uid='update_compute_config')
