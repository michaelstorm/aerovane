# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stratosphere', '0003_auto_20160616_0618'),
    ]

    operations = [
        migrations.CreateModel(
            name='AzureProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(primary_key=True, serialize=False, to='stratosphere.ProviderConfiguration', parent_link=True, auto_created=True)),
                ('cloud_service_name', models.CharField(max_length=24)),
                ('location', models.CharField(max_length=32)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='AzureProviderCredentialSet',
            fields=[
                ('providercredentialset_ptr', models.OneToOneField(primary_key=True, serialize=False, to='stratosphere.ProviderCredentialSet', parent_link=True, auto_created=True)),
                ('subscription_id', models.CharField(max_length=128)),
                ('management_certificate', models.TextField()),
            ],
            bases=('stratosphere.providercredentialset',),
        ),
        migrations.RemoveField(
            model_name='linodeproviderconfiguration',
            name='providerconfiguration_ptr',
        ),
        migrations.DeleteModel(
            name='LinodeProviderConfiguration',
        ),
        migrations.AddField(
            model_name='provider',
            name='supports_password_instance_auth',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='provider',
            name='supports_ssh_instance_auth',
            field=models.BooleanField(default=True),
            preserve_default=False,
        ),
    ]
