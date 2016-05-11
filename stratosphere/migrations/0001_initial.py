# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import stratosphere.lib.provider_configuration_status_checker
import uuid
import save_the_change.mixins
import django.db.models.deletion
import annoying.fields
import stratosphere.util
import stratosphere.lib.provider_configuration_data_loader
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthenticationMethod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('name', models.CharField(max_length=64)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(default='PENDING', choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('DESTROYED', 'Destroyed')], max_length=16)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, stratosphere.util.HasLogger, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('name', models.CharField(max_length=128)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='compute_images')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('external_id', models.CharField(null=True, max_length=256, blank=True)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(null=True, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], blank=True, max_length=16)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('destroyed', models.BooleanField(default=False)),
                ('destroyed_at', models.DateTimeField(null=True, blank=True)),
                ('failed', models.BooleanField(default=False)),
                ('failed_at', models.DateTimeField(null=True, blank=True)),
                ('failure_ignored', models.BooleanField(default=False)),
                ('group', models.ForeignKey(to='stratosphere.ComputeGroup', related_name='instances')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='DiskImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('name', models.CharField(max_length=128, db_index=True)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='DiskImageMapping',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('compute_image', models.ForeignKey(to='stratosphere.ComputeImage', related_name='disk_image_mappings')),
                ('disk_image', models.ForeignKey(to='stratosphere.DiskImage', related_name='disk_image_mappings')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Ec2ProviderCredentials',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('access_key_id', models.CharField(max_length=128)),
                ('secret_access_key', models.CharField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name='GroupInstanceStatesSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('failed', models.IntegerField()),
                ('group', models.ForeignKey(to='stratosphere.ComputeGroup', related_name='instance_states_snapshots')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalComputeGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)),
                ('created_at', models.DateTimeField(blank=True, editable=False)),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(default='PENDING', choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('DESTROYED', 'Destroyed')], max_length=16)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
            ],
            options={
                'verbose_name': 'historical compute group',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalComputeInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)),
                ('created_at', models.DateTimeField(blank=True, editable=False)),
                ('external_id', models.CharField(null=True, max_length=256, blank=True)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(null=True, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], blank=True, max_length=16)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('destroyed', models.BooleanField(default=False)),
                ('destroyed_at', models.DateTimeField(null=True, blank=True)),
                ('failed', models.BooleanField(default=False)),
                ('failed_at', models.DateTimeField(null=True, blank=True)),
                ('failure_ignored', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('group', models.ForeignKey(to='stratosphere.ComputeGroup', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL)),
            ],
            options={
                'verbose_name': 'historical compute instance',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='InstanceStatesSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('time', models.DateTimeField()),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('failed', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Provider',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('name', models.CharField(max_length=32)),
                ('pretty_name', models.CharField(max_length=32)),
                ('icon_path', models.TextField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('provider_name', models.CharField(max_length=32)),
                ('loaded', models.BooleanField(default=False)),
                ('enabled', models.BooleanField(default=True)),
            ],
            bases=(models.Model, stratosphere.lib.provider_configuration_status_checker.ProviderConfigurationStatusChecker, stratosphere.lib.provider_configuration_data_loader.ProviderConfigurationDataLoader, stratosphere.util.HasLogger, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('external_id', models.CharField(max_length=256, db_index=True)),
                ('name', models.CharField(null=True, max_length=256, db_index=True, blank=True)),
                ('extra', annoying.fields.JSONField()),
                ('disk_image', models.ForeignKey(to='stratosphere.DiskImage', null=True, related_name='provider_images', blank=True)),
                ('provider', models.ForeignKey(to='stratosphere.Provider', related_name='provider_images')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderSize',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('external_id', models.CharField(max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('price', models.DecimalField(decimal_places=5, max_digits=10)),
                ('ram', models.IntegerField()),
                ('disk', models.IntegerField()),
                ('bandwidth', models.IntegerField(null=True, blank=True)),
                ('cpu', models.IntegerField()),
                ('extra', annoying.fields.JSONField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='UserConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL, related_name='configuration')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Ec2ProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(to='stratosphere.ProviderConfiguration', primary_key=True, serialize=False, auto_created=True, parent_link=True)),
                ('region', models.CharField(max_length=16)),
                ('credentials', models.ForeignKey(to='stratosphere.Ec2ProviderCredentials', related_name='configurations')),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='KeyAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(to='stratosphere.AuthenticationMethod', primary_key=True, serialize=False, auto_created=True, parent_link=True)),
                ('key', models.TextField()),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.CreateModel(
            name='LinodeProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(to='stratosphere.ProviderConfiguration', primary_key=True, serialize=False, auto_created=True, parent_link=True)),
                ('api_key', models.CharField(max_length=128)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='PasswordAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(to='stratosphere.AuthenticationMethod', primary_key=True, serialize=False, auto_created=True, parent_link=True)),
                ('password', models.CharField(max_length=256)),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.AddField(
            model_name='providersize',
            name='provider_configuration',
            field=models.ForeignKey(to='stratosphere.ProviderConfiguration', related_name='provider_sizes'),
        ),
        migrations.AddField(
            model_name='providerimage',
            name='provider_configurations',
            field=models.ManyToManyField(related_name='provider_images', to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', editable=False, null=True, related_name='polymorphic_stratosphere.providerconfiguration_set+'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='provider',
            field=models.ForeignKey(to='stratosphere.Provider', related_name='configurations'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='user_configuration',
            field=models.ForeignKey(to='stratosphere.UserConfiguration', null=True, related_name='provider_configurations', blank=True),
        ),
        migrations.AddField(
            model_name='instancestatessnapshot',
            name='user_configuration',
            field=models.ForeignKey(to='stratosphere.UserConfiguration', related_name='instance_states_snapshots'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_configuration',
            field=models.ForeignKey(to='stratosphere.ProviderConfiguration', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_image',
            field=models.ForeignKey(to='stratosphere.ProviderImage', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_size',
            field=models.ForeignKey(to='stratosphere.ProviderSize', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='history_user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='image',
            field=models.ForeignKey(to='stratosphere.ComputeImage', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='user_configuration',
            field=models.ForeignKey(to='stratosphere.UserConfiguration', null=True, related_name='+', blank=True, on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False),
        ),
        migrations.AddField(
            model_name='groupinstancestatessnapshot',
            name='user_snapshot',
            field=models.ForeignKey(to='stratosphere.InstanceStatesSnapshot', related_name='group_snapshots'),
        ),
        migrations.AddField(
            model_name='diskimagemapping',
            name='provider',
            field=models.ForeignKey(to='stratosphere.Provider', related_name='disk_image_mappings'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_configuration',
            field=models.ForeignKey(to='stratosphere.ProviderConfiguration', related_name='instances'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_image',
            field=models.ForeignKey(to='stratosphere.ProviderImage', related_name='instances'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_size',
            field=models.ForeignKey(to='stratosphere.ProviderSize', related_name='instances'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', related_name='compute_groups'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='image',
            field=models.ForeignKey(to='stratosphere.ComputeImage', related_name='compute_groups', on_delete=django.db.models.deletion.PROTECT),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='user_configuration',
            field=models.ForeignKey(to='stratosphere.UserConfiguration', related_name='compute_groups'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', editable=False, null=True, related_name='polymorphic_stratosphere.authenticationmethod_set+'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='user_configuration',
            field=models.ForeignKey(to='stratosphere.UserConfiguration', related_name='authentication_methods'),
        ),
        migrations.AlterUniqueTogether(
            name='diskimagemapping',
            unique_together=set([('provider', 'disk_image', 'compute_image')]),
        ),
    ]
