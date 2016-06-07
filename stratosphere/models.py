from django.db import models

from simple_history.models import HistoricalRecords

from .tasks import create_libcloud_node, load_provider_data, load_public_provider_data

from .submodels.event import *
from .submodels.user import *
from .submodels.authentication_method import *
from .submodels.compute_instance import *
from .submodels.provider import *


# we have to force the actual model to be in the right module, or django-simple-history
# gets confused
class ComputeInstance(ComputeInstanceBase):
    history = HistoricalRecords()


from .submodels.image import *
from .submodels.provider_size import *
from .submodels.provider_credential_set import *
from .submodels.provider_configuration import *
from .submodels.aws.aws_provider_configuration import *
from .submodels.linode.linode_provider_configuration import *
from .submodels.compute_group import *
from .submodels.beta_key import *


class ComputeGroup(ComputeGroupBase):
    history = HistoricalRecords()


@receiver(pre_save, sender=ComputeGroup)
def compute_group_pre_save(sender, instance, raw, using, update_fields, **kwargs):
    ComputeGroup.handle_pre_save(sender, instance, raw, using, update_fields, **kwargs)


@receiver(post_save, sender=ComputeGroup)
def compute_group_post_save(sender, created, instance, **kwargs):
    ComputeGroup.handle_post_save(sender, created, instance, **kwargs)


@receiver(pre_save, sender=ComputeInstance)
def compute_instance_pre_save(sender, instance, raw, using, update_fields, **kwargs):
    ComputeInstance.handle_pre_save(sender, instance, raw, using, update_fields, **kwargs)


@receiver(post_save, sender=ComputeInstance)
def compute_instance_post_save(sender, created, instance, **kwargs):
    ComputeInstance.handle_post_save(sender, created, instance, **kwargs)


def schedule_load_provider_info(sender, created, instance, **kwargs):
    if created:
        if instance.user is None:
            schedule_random_default_delay(load_public_provider_data, instance.pk)
        else:
            schedule_random_default_delay(load_provider_data, instance.pk)


for subclass in ProviderConfiguration.__subclasses__():
    post_save.connect(schedule_load_provider_info, subclass)