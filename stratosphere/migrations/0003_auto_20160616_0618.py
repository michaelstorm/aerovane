# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid
from django.conf import settings
import stratosphere.submodels.compute_group
import stratosphere.submodels.compute_instance
import annoying.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('stratosphere', '0002_providerconfiguration_failed'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(primary_key=True, serialize=False, editable=False, default=uuid.uuid4)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='GroupCreatedEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
            ],
            bases=('stratosphere.event', stratosphere.submodels.compute_group.GroupEvent),
        ),
        migrations.CreateModel(
            name='GroupTerminatedEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
            ],
            bases=('stratosphere.event', stratosphere.submodels.compute_group.GroupEvent),
        ),
        migrations.CreateModel(
            name='InstanceFailedEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
            ],
            bases=('stratosphere.event', stratosphere.submodels.compute_instance.InstanceEvent),
        ),
        migrations.CreateModel(
            name='InstanceStateChangeEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
                ('old_state', models.CharField(max_length=16, blank=True, null=True)),
                ('new_state', models.CharField(max_length=16, blank=True, null=True)),
            ],
            bases=('stratosphere.event', stratosphere.submodels.compute_instance.InstanceEvent),
        ),
        migrations.CreateModel(
            name='ProviderConfigurationEnabledEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
                ('enabled', models.BooleanField()),
            ],
            bases=('stratosphere.event',),
        ),
        migrations.CreateModel(
            name='ProviderConfigurationFailedEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
            ],
            bases=('stratosphere.event',),
        ),
        migrations.CreateModel(
            name='RebalanceEvent',
            fields=[
                ('event_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.Event', primary_key=True)),
                ('old_size_distribution', annoying.fields.JSONField()),
                ('new_size_distribution', annoying.fields.JSONField()),
            ],
            bases=('stratosphere.event', stratosphere.submodels.compute_group.GroupEvent),
        ),
        migrations.AddField(
            model_name='event',
            name='compute_group',
            field=models.ForeignKey(to='stratosphere.ComputeGroup', null=True, related_name='events', blank=True),
        ),
        migrations.AddField(
            model_name='event',
            name='compute_instance',
            field=models.ForeignKey(to='stratosphere.ComputeInstance', null=True, related_name='events', blank=True),
        ),
        migrations.AddField(
            model_name='event',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', related_name='polymorphic_stratosphere.event_set+', null=True, editable=False),
        ),
        migrations.AddField(
            model_name='event',
            name='provider_configuration',
            field=models.ForeignKey(to='stratosphere.ProviderConfiguration', null=True, related_name='events', blank=True),
        ),
        migrations.AddField(
            model_name='event',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='events'),
        ),
        migrations.CreateModel(
            name='HailMaryEvent',
            fields=[
                ('rebalanceevent_ptr', models.OneToOneField(auto_created=True, serialize=False, parent_link=True, to='stratosphere.RebalanceEvent', primary_key=True)),
            ],
            bases=('stratosphere.rebalanceevent',),
        ),
    ]
