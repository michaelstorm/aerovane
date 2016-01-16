from django.db import models

from simple_history.models import HistoricalRecords

from .submodels.authentication_method import *
from .submodels.compute_instance import *


class Provider(models.Model):
    name = models.CharField(max_length=32)
    pretty_name = models.CharField(max_length=32)
    icon_path = models.CharField(max_length=128)


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


from .submodels.os_compute_group import *


class ImageComputeGroup(ImageComputeGroupBase):
	pass


class OperatingSystemComputeGroup(OperatingSystemComputeGroupBase):
	pass


from .submodels.user import *