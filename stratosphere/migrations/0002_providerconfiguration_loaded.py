# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stratosphere', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='providerconfiguration',
            name='loaded',
            field=models.BooleanField(default=False),
        ),
    ]
