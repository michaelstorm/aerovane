# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuid
import annoying.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('stratosphere', '0002_providerconfiguration_failed'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(editable=False, default=uuid.uuid4, serialize=False, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='GroupEvent',
            fields=[
                ('event_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.Event', auto_created=True, parent_link=True)),
            ],
            bases=('stratosphere.event',),
        ),
        migrations.CreateModel(
            name='InstanceStateChangeEvent',
            fields=[
                ('event_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.Event', auto_created=True, parent_link=True)),
                ('old_state', models.CharField(blank=True, max_length=16, null=True)),
                ('new_state', models.CharField(blank=True, max_length=16, null=True)),
            ],
            bases=('stratosphere.event',),
        ),
        migrations.AddField(
            model_name='event',
            name='compute_group',
            field=models.ForeignKey(related_name='events', to='stratosphere.ComputeGroup', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='compute_instance',
            field=models.ForeignKey(related_name='events', to='stratosphere.ComputeInstance', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', related_name='polymorphic_stratosphere.event_set+', editable=False, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='provider_configuration',
            field=models.ForeignKey(related_name='events', to='stratosphere.ProviderConfiguration', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='event',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='events'),
        ),
        migrations.CreateModel(
            name='GroupCreatedEvent',
            fields=[
                ('groupevent_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.GroupEvent', auto_created=True, parent_link=True)),
            ],
            bases=('stratosphere.groupevent',),
        ),
        migrations.CreateModel(
            name='GroupTerminatedEvent',
            fields=[
                ('groupevent_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.GroupEvent', auto_created=True, parent_link=True)),
            ],
            bases=('stratosphere.groupevent',),
        ),
        migrations.CreateModel(
            name='RebalanceEvent',
            fields=[
                ('groupevent_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.GroupEvent', auto_created=True, parent_link=True)),
                ('old_size_distribution', annoying.fields.JSONField()),
                ('new_size_distribution', annoying.fields.JSONField()),
            ],
            bases=('stratosphere.groupevent',),
        ),
        migrations.CreateModel(
            name='HailMaryEvent',
            fields=[
                ('rebalanceevent_ptr', models.OneToOneField(serialize=False, primary_key=True, to='stratosphere.RebalanceEvent', auto_created=True, parent_link=True)),
            ],
            bases=('stratosphere.rebalanceevent',),
        ),
    ]
