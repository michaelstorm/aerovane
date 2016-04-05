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
from .submodels.ec2.ec2_provider_configuration import *
from .submodels.linode.linode_provider_configuration import *
from .submodels.compute_group import *


class ComputeGroup(ComputeGroupBase):
    history = HistoricalRecords()


from .submodels.user import *


@receiver(pre_save, sender=ComputeInstance)
def compute_instance_pre_save(sender, instance, raw, using, update_fields, **kwargs):
    ComputeInstance.handle_pre_save(sender, instance, raw, using, update_fields, **kwargs)


@receiver(post_save, sender=ComputeInstance)
def compute_instance_post_save(sender, created, instance, **kwargs):
    ComputeInstance.handle_post_save(sender, created, instance, **kwargs)