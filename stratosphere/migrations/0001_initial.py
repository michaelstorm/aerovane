# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import annoying.fields
import django.db.models.deletion
import stratosphere.util
import stratosphere.submodels.beta_key
import django.utils.timezone
from django.conf import settings
import uuid
import stratosphere.lib.provider_configuration_data_loader
import stratosphere.lib.provider_configuration_status_checker
import stratosphere.submodels.user
import save_the_change.mixins


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0006_require_contenttypes_0002'),
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('password', models.CharField(verbose_name='password', max_length=128)),
                ('last_login', models.DateTimeField(null=True, blank=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status', default=False)),
                ('first_name', models.CharField(blank=True, verbose_name='first name', max_length=30)),
                ('last_name', models.CharField(blank=True, verbose_name='last name', max_length=30)),
                ('email', models.EmailField(unique=True, verbose_name='email address', max_length=255, db_index=True)),
                ('is_staff', models.BooleanField(help_text='Designates whether the user can log into this admin site.', verbose_name='staff status', default=False)),
                ('is_active', models.BooleanField(help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active', default=True)),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('groups', models.ManyToManyField(related_query_name='user', blank=True, related_name='user_set', to='auth.Group', help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(related_query_name='user', blank=True, related_name='user_set', to='auth.Permission', help_text='Specific permissions for this user.', verbose_name='user permissions')),
            ],
            options={
                'verbose_name_plural': 'users',
                'verbose_name': 'user',
            },
            managers=[
                ('objects', stratosphere.submodels.user.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name='AuthenticationMethod',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('name', models.CharField(max_length=64)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='BetaKey',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('value', models.CharField(default=stratosphere.submodels.beta_key._create_beta_key_value, max_length=16)),
                ('note', models.CharField(default='', max_length=256)),
                ('user', models.ForeignKey(null=True, blank=True, related_name='beta_keys', to=settings.AUTH_USER_MODEL)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeGroup',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
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
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('name', models.CharField(max_length=128)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='compute_images')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ComputeInstance',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('external_id', models.CharField(null=True, blank=True, max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(null=True, blank=True, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], max_length=16)),
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
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('name', models.CharField(null=True, blank=True, max_length=128, db_index=True)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='DiskImageMapping',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('compute_image', models.ForeignKey(to='stratosphere.ComputeImage', related_name='disk_image_mappings')),
                ('disk_image', models.ForeignKey(to='stratosphere.DiskImage', related_name='disk_image_mappings')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='GroupInstanceStatesSnapshot',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
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
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical compute group',
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalComputeInstance',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)),
                ('created_at', models.DateTimeField(blank=True, editable=False)),
                ('external_id', models.CharField(null=True, blank=True, max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('state', models.CharField(null=True, blank=True, choices=[('RUNNING', 'Running'), ('REBOOTING', 'Rebooting'), ('TERMINATED', 'Terminated'), ('PENDING', 'Pending'), ('STOPPED', 'Stopped'), ('SUSPENDED', 'Suspended'), ('PAUSED', 'Paused'), ('ERROR', 'Error'), ('UNKNOWN', 'Unknown')], max_length=16)),
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
                ('group', models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.ComputeGroup')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'verbose_name': 'historical compute instance',
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='InstanceStatesSnapshot',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('time', models.DateTimeField()),
                ('pending', models.IntegerField()),
                ('running', models.IntegerField()),
                ('failed', models.IntegerField()),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='instance_states_snapshots')),
            ],
        ),
        migrations.CreateModel(
            name='Provider',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('name', models.CharField(max_length=32)),
                ('pretty_name', models.CharField(max_length=32)),
                ('icon_path', models.TextField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderConfiguration',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('provider_name', models.CharField(max_length=32)),
                ('data_state', models.CharField(default='NOT_LOADED', choices=[('NOT_LOADED', 'Not loaded'), ('LOADED', 'Loaded'), ('ERROR', 'Error')], max_length=16)),
                ('enabled', models.BooleanField(default=True)),
            ],
            bases=(models.Model, stratosphere.lib.provider_configuration_status_checker.ProviderConfigurationStatusChecker, stratosphere.lib.provider_configuration_data_loader.ProviderConfigurationDataLoader, stratosphere.util.HasLogger, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderCredentialSet',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('error_type', models.CharField(null=True, blank=True, choices=[('INVALID_CREDENTIALS', 'INVALID_CREDENTIALS'), ('UNAUTHORIZED_CREDENTIALS', 'UNAUTHORIZED_CREDENTIALS'), ('UNKNOWN_ERROR', 'UNKNOWN_ERROR')], max_length=24)),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderImage',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('external_id', models.CharField(max_length=256, db_index=True)),
                ('name', models.CharField(null=True, blank=True, max_length=256, db_index=True)),
                ('extra', annoying.fields.JSONField()),
                ('disk_image', models.ForeignKey(null=True, blank=True, related_name='provider_images', to='stratosphere.DiskImage')),
                ('provider', models.ForeignKey(to='stratosphere.Provider', related_name='provider_images')),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='ProviderSize',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, serialize=False, editable=False)),
                ('external_id', models.CharField(max_length=256)),
                ('name', models.CharField(max_length=256)),
                ('price', models.DecimalField(max_digits=10, decimal_places=5)),
                ('ram', models.IntegerField()),
                ('disk', models.IntegerField()),
                ('bandwidth', models.IntegerField(null=True, blank=True)),
                ('cpu', models.IntegerField()),
                ('extra', annoying.fields.JSONField()),
            ],
            bases=(models.Model, save_the_change.mixins.SaveTheChange, save_the_change.mixins.TrackChanges),
        ),
        migrations.CreateModel(
            name='AWSProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(auto_created=True, primary_key=True, parent_link=True, serialize=False, to='stratosphere.ProviderConfiguration')),
                ('region', models.CharField(max_length=16)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='AWSProviderCredentialSet',
            fields=[
                ('providercredentialset_ptr', models.OneToOneField(auto_created=True, primary_key=True, parent_link=True, serialize=False, to='stratosphere.ProviderCredentialSet')),
                ('access_key_id', models.CharField(max_length=128)),
                ('secret_access_key', models.CharField(max_length=128)),
            ],
            bases=('stratosphere.providercredentialset',),
        ),
        migrations.CreateModel(
            name='KeyAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(auto_created=True, primary_key=True, parent_link=True, serialize=False, to='stratosphere.AuthenticationMethod')),
                ('key', models.TextField()),
            ],
            bases=('stratosphere.authenticationmethod',),
        ),
        migrations.CreateModel(
            name='LinodeProviderConfiguration',
            fields=[
                ('providerconfiguration_ptr', models.OneToOneField(auto_created=True, primary_key=True, parent_link=True, serialize=False, to='stratosphere.ProviderConfiguration')),
                ('api_key', models.CharField(max_length=128)),
            ],
            bases=('stratosphere.providerconfiguration',),
        ),
        migrations.CreateModel(
            name='PasswordAuthenticationMethod',
            fields=[
                ('authenticationmethod_ptr', models.OneToOneField(auto_created=True, primary_key=True, parent_link=True, serialize=False, to='stratosphere.AuthenticationMethod')),
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
            field=models.ManyToManyField(to='stratosphere.ProviderConfiguration', related_name='provider_images'),
        ),
        migrations.AddField(
            model_name='providercredentialset',
            name='polymorphic_ctype',
            field=models.ForeignKey(null=True, related_name='polymorphic_stratosphere.providercredentialset_set+', to='contenttypes.ContentType', editable=False),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='polymorphic_ctype',
            field=models.ForeignKey(null=True, related_name='polymorphic_stratosphere.providerconfiguration_set+', to='contenttypes.ContentType', editable=False),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='provider',
            field=models.ForeignKey(to='stratosphere.Provider', related_name='configurations'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='provider_credential_set',
            field=models.ForeignKey(to='stratosphere.ProviderCredentialSet', related_name='provider_configurations'),
        ),
        migrations.AddField(
            model_name='providerconfiguration',
            name='user',
            field=models.ForeignKey(null=True, blank=True, related_name='provider_configurations', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_configuration',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.ProviderConfiguration'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_image',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.ProviderImage'),
        ),
        migrations.AddField(
            model_name='historicalcomputeinstance',
            name='provider_size',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.ProviderSize'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='authentication_method',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.AuthenticationMethod'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='history_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='image',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to='stratosphere.ComputeImage'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='user',
            field=models.ForeignKey(null=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, blank=True, related_name='+', to=settings.AUTH_USER_MODEL),
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
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='compute_groups', to='stratosphere.ComputeImage'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='compute_groups'),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='polymorphic_ctype',
            field=models.ForeignKey(null=True, related_name='polymorphic_stratosphere.authenticationmethod_set+', to='contenttypes.ContentType', editable=False),
        ),
        migrations.AddField(
            model_name='authenticationmethod',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='authentication_methods'),
        ),
        migrations.AlterUniqueTogether(
            name='diskimagemapping',
            unique_together=set([('provider', 'disk_image', 'compute_image')]),
        ),
    ]
