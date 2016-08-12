# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def add_azure_provider(apps, schema_editor):
    Provider = apps.get_model("stratosphere", "Provider")
    Provider.objects.create(
                name='azure_south_central_us',
                pretty_name='Azure South Central US',
                icon_path='stratosphere/azure_icon.png',
                supports_password_instance_auth=True,
                supports_ssh_instance_auth=False)


class Migration(migrations.Migration):

    dependencies = [
        ('stratosphere', '0004_auto_20160807_0443'),
    ]

    operations = [
        migrations.RunPython(add_azure_provider),
    ]
