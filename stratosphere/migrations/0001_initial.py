# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import stratosphere.lib.provider_configuration_data_loader
from django.conf import settings
import save_the_change.mixins
import annoying.fields
import stratosphere.lib.provider_configuration_status_checker
import uuid
import django.db.models.deletion
import stratosphere.util


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(default='PENDING', choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('TERMINATED', 'Terminated')], max_length=16)),
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
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('external_id', models.CharField(blank=True, null=True, max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], null=True, blank=True, max_length=16)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('last_state_update_time', models.DateTimeField()),
                ('terminated', models.BooleanField(default=False)),
                ('failed', models.BooleanField(default=False)),
                ('failure_ignored', models.BooleanField(default=False)),
                ('group', models.ForeignKey(related_name='instances', to='stratosphere.ComputeGroup')),
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
                ('name', models.CharField(db_index=True, max_length=128)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='DiskImageMapping',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('compute_image', models.ForeignKey(related_name='disk_image_mappings', to='stratosphere.ComputeImage')),
                ('disk_image', models.ForeignKey(related_name='disk_image_mappings', to='stratosphere.DiskImage')),
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
                ('terminated', models.IntegerField()),
                ('group', models.ForeignKey(related_name='instance_states_snapshots', to='stratosphere.ComputeGroup')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalComputeGroup',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(default='PENDING', choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('TERMINATED', 'Terminated')], max_length=16)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical compute group',
            },
        ),
        migrations.CreateModel(
            name='HistoricalComputeInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)),
                ('external_id', models.CharField(blank=True, null=True, max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], null=True, blank=True, max_length=16)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('last_state_update_time', models.DateTimeField()),
                ('terminated', models.BooleanField(default=False)),
                ('failed', models.BooleanField(default=False)),
                ('failure_ignored', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('group', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ComputeGroup', null=True, db_constraint=False, blank=True)),
                ('history_user', models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical compute instance',
            },
        ),
        migrations.CreateModel(
            name='InstanceStatesSnapshot',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('time', models.DateTimeField()),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('terminated', models.IntegerField()),
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
                ('external_id', models.CharField(db_index=True, max_length=256)),
                ('name', models.CharField(db_index=True, null=True, blank=True, max_length=256)),
                ('extra', annoying.fields.JSONField()),
                ('disk_image', models.ForeignKey(related_name='provider_images', to='stratosphere.DiskImage', null=True, blank=True)),
                ('provider', models.ForeignKey(related_name='provider_images', to='stratosphere.Provider')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderSize',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('external_id', models.CharField(max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('price', models.FloatField()),
                ('ram', models.IntegerField()),
                ('disk', models.IntegerField()),
                ('bandwidth', models.IntegerField(blank=True, null=True)),
                ('cpu', models.IntegerField()),
                ('extra', annoying.fields.JSONField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='UserConfiguration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False, editable=False)),
                ('user', models.OneToOneField(related_name='configuration', to=settings.AUTH_USER_MODEL)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Ec2ProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(parent_link=True, to='stratosphere.ProviderConfiguration', primary_key=True, serialize=False, auto_created=True)),
                ('region', models.CharField(max_length=16)),
                ('credentials', models.ForeignKey(related_name='configurations', to='stratosphere.Ec2ProviderCredentials')),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='KeyAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(parent_link=True, to='stratosphere.AuthenticationMethod', primary_key=True, serialize=False, auto_created=True)),
                ('key', models.TextField()),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.CreateModel(
            name='LinodeProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(parent_link=True, to='stratosphere.ProviderConfiguration', primary_key=True, serialize=False, auto_created=True)),
                ('api_key', models.CharField(max_length=128)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='PasswordAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(parent_link=True, to='stratosphere.AuthenticationMethod', primary_key=True, serialize=False, auto_created=True)),
                ('password', models.CharField(max_length=256)),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.AddField(
            model_name='providersize',
            name='provider_configuration',
            field=models.ForeignKey(related_name='provider_sizes', to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='providerimage',
            name='provider_configurations',
            field=models.ManyToManyField(related_name='provider_images', to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_stratosphere.providerconfiguration_set+', editable=False, null=True, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='provider',
            field=models.ForeignKey(related_name='configurations', to='stratosphere.Provider'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='user_configuration',
            field=models.ForeignKey(related_name='provider_configurations', to='stratosphere.UserConfiguration', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='instancestatessnapshot',
            name='user_configuration',
            field=models.ForeignKey(related_name='instance_states_snapshots', to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_configuration',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderConfiguration', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderImage', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_size',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderSize', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='authentication_method',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.AuthenticationMethod', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='history_user',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='image',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ComputeImage', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='user_configuration',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.UserConfiguration', null=True, db_constraint=False, blank=True),
        ),
        migrations.AddField(
            model_name='groupinstancestatessnapshot',
            name='user_snapshot',
            field=models.ForeignKey(related_name='group_snapshots', to='stratosphere.InstanceStatesSnapshot'),
        ),
        migrations.AddField(
            model_name='diskimagemapping',
            name='provider',
            field=models.ForeignKey(related_name='disk_image_mappings', to='stratosphere.Provider'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_configuration',
            field=models.ForeignKey(related_name='instances', to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_image',
            field=models.ForeignKey(related_name='instances', to='stratosphere.ProviderImage'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='provider_size',
            field=models.ForeignKey(related_name='instances', to='stratosphere.ProviderSize'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='authentication_method',
            field=models.ForeignKey(related_name='compute_groups', to='stratosphere.AuthenticationMethod'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='image',
            field=models.ForeignKey(related_name='compute_groups', to='stratosphere.ComputeImage'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='user_configuration',
            field=models.ForeignKey(related_name='compute_groups', to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_stratosphere.authenticationmethod_set+', editable=False, null=True, to='contenttypes.ContentType'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='user_configuration',
            field=models.ForeignKey(related_name='authentication_methods', to='stratosphere.UserConfiguration'),
        ),
        migrations.AlterUniqueTogether(
            name='diskimagemapping',
            unique_together=set([('provider', 'disk_image', 'compute_image')]),
        ),
    ]
