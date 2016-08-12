# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


def migrate_authentication_methods(apps, schema_editor):
    ComputeGroup = apps.get_model("stratosphere", "ComputeGroup")
    for group in ComputeGroup.objects.all():
        group.key_authentication_method = group.authentication_method
        group.save()


class Migration(migrations.Migration):

    dependencies = [
        ('stratosphere', '0005_auto_20160807_0445'),
    ]

    operations = [
        migrations.AddField(
            model_name='computegroup',
            name='key_authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', blank=True, null=True, related_name='key_compute_groups'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='password_authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', blank=True, null=True, related_name='password_compute_groups'),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='key_authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', blank=True, db_constraint=False, null=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING),
        ),
        migrations.AddField(
            model_name='historicalcomputegroup',
            name='password_authentication_method',
            field=models.ForeignKey(to='stratosphere.AuthenticationMethod', blank=True, db_constraint=False, null=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING),
        ),
        migrations.RunPython(migrate_authentication_methods),
        migrations.RemoveField(
            model_name='computegroup',
            name='authentication_method',
        ),
    ]
