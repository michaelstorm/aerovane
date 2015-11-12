from django.contrib import admin

from .models import *


class ProviderConfigurationInline(admin.TabularInline):
    model = ProviderConfiguration


class UserConfigurationAdmin(admin.ModelAdmin):
    inlines = [ProviderConfigurationInline]


admin.site.register(ComputeInstanceType)
admin.site.register(ComputeGroup)
admin.site.register(Ec2ComputeInstance)
admin.site.register(LinodeComputeInstance)
admin.site.register(Ec2ProviderConfiguration)
admin.site.register(UserConfiguration, UserConfigurationAdmin)
