from django import forms
from django.contrib import admin

from .models import *


class ProviderConfigurationInline(admin.TabularInline):
    model = ProviderConfiguration
    extra = 0


class UserConfigurationAdmin(admin.ModelAdmin):
    inlines = [ProviderConfigurationInline]


class ProviderSizeAdmin(admin.ModelAdmin):
    model = ProviderSize
    search_fields = ['external_id', 'name']


admin.site.register(DiskImage)
admin.site.register(OperatingSystemImage)
admin.site.register(ProviderImage)
admin.site.register(ProviderSize, ProviderSizeAdmin)
admin.site.register(ComputeGroup)
admin.site.register(ComputeInstance)
admin.site.register(Ec2ProviderConfiguration)
admin.site.register(UserConfiguration, UserConfigurationAdmin)
