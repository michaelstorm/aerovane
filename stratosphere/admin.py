from django import forms
from django.contrib import admin

from polymorphic.admin import PolymorphicParentModelAdmin, PolymorphicChildModelAdmin

from .models import *


class ProviderConfigurationInline(admin.TabularInline):
    model = ProviderConfiguration
    extra = 0


class UserConfigurationAdmin(admin.ModelAdmin):
    inlines = [ProviderConfigurationInline]


class ProviderImageInline(admin.TabularInline):
    model = ProviderImage
    extra = 0


class ImageChildAdmin(PolymorphicChildModelAdmin):
    """ Base admin class for all child models """
    base_model = Image
    base_fieldsets = (
        (None, {
            'fields': ('name',)
        }),
    )


class DiskImageAdmin(ImageChildAdmin):
    base_model = DiskImage
    inlines = [ProviderImageInline]


class OperatingSystemImageAdmin(ImageChildAdmin):
    base_model = OperatingSystemImage
    base_fieldsets = (
        (None, {
            'fields': ('disk_images',)
        }),
    )


class ImageParentAdmin(PolymorphicParentModelAdmin):
    """ The parent model admin """
    base_model = Image
    child_models = (
        (DiskImage, DiskImageAdmin),
        (OperatingSystemImage, OperatingSystemImageAdmin),
    )

    search_fields = ['name']


class ProviderSizeAdmin(admin.ModelAdmin):
    model = ProviderSize
    search_fields = ['external_id', 'name']

admin.site.register(Image, ImageParentAdmin)

admin.site.register(ProviderImage)
admin.site.register(ProviderSize, ProviderSizeAdmin)
admin.site.register(ComputeGroup)
admin.site.register(ComputeInstance)
admin.site.register(Ec2ProviderConfiguration)
admin.site.register(UserConfiguration, UserConfigurationAdmin)
