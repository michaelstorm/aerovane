from django.contrib import admin

from .models import *


admin.site.register(ComputeInstanceType)
admin.site.register(ComputeGroup)
admin.site.register(Ec2ComputeInstance)
admin.site.register(LinodeComputeInstance)
