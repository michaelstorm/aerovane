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