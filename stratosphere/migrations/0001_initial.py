# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import stratosphere.util
import uuid
import save_the_change.mixins
import django.db.models.deletion
from django.conf import settings
import annoying.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuthenticationMethod',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=64)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeGroup',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(max_length=16, choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('TERMINATED', 'Terminated')], default='PENDING')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model, stratosphere.util.HasLogger, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeInstance',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('external_id', models.CharField(max_length=256, null=True, blank=True)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(max_length=16, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], null=True, blank=True)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('last_state_update_time', models.DateTimeField()),
                ('terminated', models.BooleanField(default=False)),
                ('failed_at', models.DateTimeField(null=True, blank=True)),
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
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('name', models.CharField(max_length=128, db_index=True)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='DiskImageMapping',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('disk_image', models.ForeignKey(related_name='disk_image_mappings', to='stratosphere.DiskImage')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Ec2ProviderCredentials',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('access_key_id', models.CharField(max_length=128)),
                ('secret_access_key', models.CharField(max_length=128)),
            ],
        ),
        migrations.CreateModel(
            name='GroupInstanceStatesSnapshot',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('terminated', models.IntegerField()),
                ('group', models.ForeignKey(related_name='instance_states_snapshots', to='stratosphere.ComputeGroup')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalComputeGroup',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', annoying.fields.JSONField()),
                ('size_distribution', annoying.fields.JSONField()),
                ('state', models.CharField(max_length=16, choices=[('PENDING', 'Pending'), ('RUNNING', 'Running'), ('TERMINATED', 'Terminated')], default='PENDING')),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical compute group',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='HistoricalComputeInstance',
            fields=[
                ('id', models.IntegerField(blank=True, verbose_name='ID', auto_created=True, db_index=True)),
                ('external_id', models.CharField(max_length=256, null=True, blank=True)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(max_length=16, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], null=True, blank=True)),
                ('public_ips', annoying.fields.JSONField()),
                ('private_ips', annoying.fields.JSONField()),
                ('extra', annoying.fields.JSONField()),
                ('last_state_update_time', models.DateTimeField()),
                ('terminated', models.BooleanField(default=False)),
                ('failed_at', models.DateTimeField(null=True, blank=True)),
                ('failure_ignored', models.BooleanField(default=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('group', models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ComputeGroup')),
                ('history_user', models.ForeignKey(null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical compute instance',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='InstanceStatesSnapshot',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('time', models.DateTimeField()),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('terminated', models.IntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='OperatingSystemImage',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=128)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Provider',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('name', models.CharField(max_length=32)),
                ('pretty_name', models.CharField(max_length=32)),
                ('icon_path', models.TextField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderConfiguration',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('provider_name', models.CharField(max_length=32)),
                ('loaded', models.BooleanField(default=False)),
                ('enabled', models.BooleanField(default=True)),
            ],
            bases=(models.Model, stratosphere.util.HasLogger, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderImage',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ('external_id', models.CharField(max_length=256, db_index=True)),
                ('name', models.CharField(max_length=256, db_index=True, null=True, blank=True)),
                ('extra', annoying.fields.JSONField()),
                ('disk_image', models.ForeignKey(null=True, blank=True, related_name='provider_images', to='stratosphere.DiskImage')),
                ('provider', models.ForeignKey(related_name='provider_images', to='stratosphere.Provider')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderSize',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('external_id', models.CharField(max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('price', models.FloatField()),
                ('ram', models.IntegerField()),
                ('disk', models.IntegerField()),
                ('bandwidth', models.IntegerField(null=True, blank=True)),
                ('vcpus', models.IntegerField(null=True, blank=True)),
                ('extra', annoying.fields.JSONField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='UserConfiguration',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('user', models.OneToOneField(to=settings.AUTH_USER_MODEL, related_name='configuration')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='Ec2ProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(primary_key=True, auto_created=True, to='stratosphere.ProviderConfiguration', parent_link=True, serialize=False)),
                ('region', models.CharField(max_length=16)),
                ('credentials', models.ForeignKey(related_name='configurations', to='stratosphere.Ec2ProviderCredentials')),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='KeyAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(primary_key=True, auto_created=True, to='stratosphere.AuthenticationMethod', parent_link=True, serialize=False)),
                ('key', models.TextField()),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.CreateModel(
            name='LinodeProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(primary_key=True, auto_created=True, to='stratosphere.ProviderConfiguration', parent_link=True, serialize=False)),
                ('api_key', models.CharField(max_length=128)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='PasswordAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(primary_key=True, auto_created=True, to='stratosphere.AuthenticationMethod', parent_link=True, serialize=False)),
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
            field=models.ForeignKey(null=True, editable=False, to='contenttypes.ContentType', related_name='polymorphic_stratosphere.providerconfiguration_set+'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='provider',
            field=models.ForeignKey(related_name='configurations', to='stratosphere.Provider'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='user_configuration',
            field=models.ForeignKey(null=True, blank=True, related_name='provider_configurations', to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='instancestatessnapshot',
            name='user_configuration',
            field=models.ForeignKey(related_name='instance_states_snapshots', to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_configuration',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_image',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderImage'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_size',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.ProviderSize'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='authentication_method',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.AuthenticationMethod'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='history_user',
            field=models.ForeignKey(null=True, related_name='+', on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='image',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.OperatingSystemImage'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='user_configuration',
            field=models.ForeignKey(db_constraint=False, null=True, blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='groupinstancestatessnapshot',
            name='user_snapshot',
            field=models.ForeignKey(related_name='group_snapshots', to='stratosphere.InstanceStatesSnapshot'),
        ),
        migrations.AddField(
            model_name='diskimagemapping',
            name='operating_system_image',
            field=models.ForeignKey(related_name='disk_image_mappings', to='stratosphere.OperatingSystemImage'),
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
            field=models.ForeignKey(related_name='compute_groups', to='stratosphere.OperatingSystemImage'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='user_configuration',
            field=models.ForeignKey(related_name='compute_groups', to='stratosphere.UserConfiguration'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='polymorphic_ctype',
            field=models.ForeignKey(null=True, editable=False, to='contenttypes.ContentType', related_name='polymorphic_stratosphere.authenticationmethod_set+'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='user_configuration',
            field=models.ForeignKey(related_name='authentication_methods', to='stratosphere.UserConfiguration'),
        ),
        migrations.AlterUniqueTogether(
            name='diskimagemapping',
            unique_together=set([('provider', 'disk_image', 'operating_system_image')]),
        ),
    ]
