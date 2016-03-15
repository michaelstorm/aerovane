from django.db import models

from simple_history.models import HistoricalRecords

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


@receiver(pre_save, sender=ComputeGroup)
def set_state_updated_time(sender, instance, raw, using, update_fields, **kwargs):
    if instance.id:
        old_instance = ComputeGroup.objects.get(pk=instance.id)
        if instance.state != old_instance.state:
            instance.last_state_update_time = timezone.now()
    # instance is being created
    else:
        instance.last_state_update_time = timezone.now()