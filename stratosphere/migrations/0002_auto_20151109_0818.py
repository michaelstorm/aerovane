# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('stratosphere', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ComputeGroup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('instance_count', models.IntegerField()),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('name', models.CharField(max_length=128)),
                ('provider_policy', models.TextField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ComputeInstance',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('external_id', models.CharField(max_length=256)),
                ('provider', models.CharField(max_length=256, choices=[('aws', 'Amazon Web Services'), ('azure', 'Microsoft Azure'), ('linode', 'Linode'), ('digitalocean', 'DigitalOcean'), ('softlayer', 'SoftLayer'), ('cloudsigma', 'CloudSigma'), ('google', 'Google App Engine')])),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ComputeInstanceType',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, auto_created=True, verbose_name='ID')),
                ('provider', models.CharField(max_length=32, choices=[('aws', 'Amazon Web Services'), ('azure', 'Microsoft Azure'), ('linode', 'Linode'), ('digitalocean', 'DigitalOcean'), ('softlayer', 'SoftLayer'), ('cloudsigma', 'CloudSigma'), ('google', 'Google App Engine')])),
                ('name', models.CharField(max_length=32)),
                ('cpu', models.IntegerField()),
                ('memory', models.IntegerField()),
                ('attached_storage', models.IntegerField()),
                ('hour_price', models.IntegerField()),
                ('external_id', models.CharField(max_length=32)),
                ('polymorphic_ctype', models.ForeignKey(to='contenttypes.ContentType', editable=False, null=True, related_name='polymorphic_stratosphere.computeinstancetype_set+')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Ec2ComputeInstance',
            fields=[
                ('computeinstance_ptr', models.OneToOneField(serialize=False, to='stratosphere.ComputeInstance', primary_key=True, parent_link=True, auto_created=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('stratosphere.computeinstance',),
        ),
        migrations.CreateModel(
            name='ImageComputeGroup',
            fields=[
                ('computegroup_ptr', models.OneToOneField(serialize=False, to='stratosphere.ComputeGroup', primary_key=True, parent_link=True, auto_created=True)),
                ('image_id', models.CharField(max_length=64)),
            ],
            options={
                'abstract': False,
            },
            bases=('stratosphere.computegroup',),
        ),
        migrations.CreateModel(
            name='LinodeComputeInstance',
            fields=[
                ('computeinstance_ptr', models.OneToOneField(serialize=False, to='stratosphere.ComputeInstance', primary_key=True, parent_link=True, auto_created=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('stratosphere.computeinstance',),
        ),
        migrations.CreateModel(
            name='OsComputeGroup',
            fields=[
                ('computegroup_ptr', models.OneToOneField(serialize=False, to='stratosphere.ComputeGroup', primary_key=True, parent_link=True, auto_created=True)),
                ('os', models.CharField(max_length=64)),
            ],
            options={
                'abstract': False,
            },
            bases=('stratosphere.computegroup',),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='group',
            field=models.ForeignKey(null=True, to='stratosphere.ComputeGroup', blank=True, related_name='instances'),
        ),
        migrations.AddField(
            model_name='computeinstance',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', editable=False, null=True, related_name='polymorphic_stratosphere.computeinstance_set+'),
        ),
        migrations.AddField(
            model_name='computegroup',
            name='polymorphic_ctype',
            field=models.ForeignKey(to='contenttypes.ContentType', editable=False, null=True, related_name='polymorphic_stratosphere.computegroup_set+'),
        ),
    ]
