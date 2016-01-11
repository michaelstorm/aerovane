from django.db import models


class Provider(models.Model):
    name = models.CharField(max_length=32)
    pretty_name = models.CharField(max_length=32)
    icon_path = models.CharField(max_length=128)


from .submodels.authentication_method import *
from .submodels.compute_instance import *
from .submodels.image import *
from .submodels.provider_size import *
from .submodels.provider_configuration import *
from .submodels.compute_group import *
from .submodels.user import *