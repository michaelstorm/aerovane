from django.db import models

from simple_history.models import HistoricalRecords

from .tasks import create_libcloud_node

from .submodels.authentication_method import *
from .submodels.compute_instance import *
from .submodels.provider import *


# we have to force the actual model to be in the right module, or django-simple-history
# gets confused
class ComputeInstance(ComputeInstanceBase):
    history = HistoricalRecords()


from .submodels.image import *
from .submodels.provider_size import *
from .submodels.provider_configuration import *
from .submodels.compute_group import *


class ComputeGroup(ComputeGroupBase):
    history = HistoricalRecords()


from .submodels.user import *


@receiver(pre_save, sender=ComputeInstance)
def set_state_updated_time(sender, instance, raw, using, update_fields, **kwargs):
    if instance.id:
        old_instance = ComputeInstance.objects.get(pk=instance.id)
        if instance.state != old_instance.state:
            instance.last_state_update_time = timezone.now()
    else:
        # instance is being created
        instance.last_state_update_time = timezone.now()


@receiver(post_save, sender=ComputeInstance)
def schedule_create_libcloud_node_job(sender, created, instance, **kwargs):
    if created:
        schedule_random_default_delay(create_libcloud_node, instance.pk)