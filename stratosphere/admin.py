from django import forms
from django.contrib import admin

from .models import *


class ProviderSizeAdmin(admin.ModelAdmin):
    model = ProviderSize
    search_fields = ['external_id', 'name']


class PasswordAuthenticationMethodAdmin(admin.ModelAdmin):
    def get_fields(self, request, obj=None):
        fields = super(PasswordAuthenticationMethodAdmin, self).get_fields(request, obj)
        if obj is not None:
            fields.remove('password')
        return fields


admin.site.register(ComputeGroup)
admin.site.register(ComputeImage)
admin.site.register(ComputeInstance)
admin.site.register(DiskImage)
admin.site.register(AWSProviderConfiguration)
admin.site.register(KeyAuthenticationMethod)
admin.site.register(PasswordAuthenticationMethod, PasswordAuthenticationMethodAdmin)
admin.site.register(ProviderImage)
admin.site.register(ProviderSize, ProviderSizeAdmin)
admin.site.register(UserConfiguration)
