from celery.task.schedules import crontab
from celery.decorators import periodic_task

from datetime import datetime, timedelta

from django.db import connection, OperationalError, transaction
from django.db.models import Q
from django.utils import timezone

from libcloud.compute.base import Node, NodeAuthPassword, NodeAuthSSHKey

import json

from multicloud.celery import app

import random

from .util import NodeJSONEncoder, schedule_random_default_delay, thread_local

# we don't import import models here, since doing so seems to screw up bootstrapping


@app.task()
def load_provider_data(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    if provider_configuration.user_configuration is None:
        provider_configuration.load_data(True)
    else:
        provider_configuration.load_data(False)


@periodic_task(run_every=timedelta(minutes=10))
def update_provider_info_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.all().values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(load_provider_data, provider_configuration_id)


@app.task()
def check_failed_instances(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.check_failed_instances()


@periodic_task(run_every=timedelta(seconds=10))
def check_failed_instances_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.all().values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(check_failed_instances, provider_configuration_id)


@app.task()
def check_provider_enabled(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.check_enabled()


@periodic_task(run_every=timedelta(seconds=10))
def check_provider_enabled_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.all().values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(check_provider_enabled, provider_configuration_id)


@app.task()
def check_instance_states_snapshots(user_configuration_id):
    from .models import UserConfiguration

    user_configuration = UserConfiguration.objects.get(pk=user_configuration_id)
    user_configuration.take_instance_states_snapshot_if_changed()


@periodic_task(run_every=timedelta(seconds=15))
def check_instance_states_snapshots_all():
    from .models import UserConfiguration

    user_configuration_ids = UserConfiguration.objects.all().values_list('pk', flat=True)
    for user_configuration_id in user_configuration_ids:
        check_instance_states_snapshots.delay(user_configuration_id)


@app.task()
def check_instance_distribution(compute_group_id):
    from .models import ComputeGroup

    compute_group = ComputeGroup.objects.get(pk=compute_group_id)
    compute_group.check_instance_distribution()


@periodic_task(run_every=timedelta(seconds=10))
def check_instance_distribution_all():
    from .models import ComputeGroup

    compute_group_ids = ComputeGroup.objects.all().values_list('pk', flat=True)
    for compute_group_id in compute_group_ids:
        schedule_random_default_delay(check_instance_distribution, compute_group_id)


@app.task()
def update_instance_statuses(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.update_instance_statuses()


@periodic_task(run_every=timedelta(seconds=10))
def update_instance_statuses_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.all().values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(update_instance_statuses, provider_configuration_id)


@periodic_task(run_every=timedelta(seconds=30))
def clean_up_destroyed_instances():
    from .models import ComputeInstance

    two_minutes_ago = timezone.now() - timedelta(minutes=2)
    destroyed = Q(destroyed=True, destroyed_at__lt=two_minutes_ago)
    failed = Q(failed=True)
    not_terminated = ~Q(state=ComputeInstance.TERMINATED)
    query = (destroyed | failed) & not_terminated

    leftover_instances = ComputeInstance.objects.filter(query)
    for instance in leftover_instances:
        print('Destroying leftover instance %s' % instance.pk)
        destroy_libcloud_node.delay(instance.pk)


@app.task()
def destroy_libcloud_node(compute_instance_id):
    from .models import ComputeInstance

    instance = ComputeInstance.objects.get(pk=compute_instance_id)

    if instance.external_id is None:
        print('No external_id for instance %s; not destroying libcloud node' % instance.pk)
    else:
        instance.provider_configuration.destroy_libcloud_node(instance.to_libcloud_node())


# TODO not sure whether this should be kept
# @periodic_task(run_every=timedelta(minutes=4))
def recreate_stale_pending_instances():
    from .models import ComputeInstance

    two_minutes_ago = timezone.now() - timedelta(minutes=2)
    query = ComputeInstance.pending_instances_query() & Q(created_at__lt=two_minutes_ago)
    stale_pending_instances = ComputeInstance.objects.filter(query)

    print('Found %d stale pending instances' % stale_pending_instances.count())
    for instance in stale_pending_instances:
        print('Pending instance %s is stale' % instance.pk)
        compute_instance_args = {
            'name': instance.name,
            'provider_image': instance.provider_image,
            'group': instance.group,
            'provider_size': instance.provider_size,
            'extra': {},
            'provider_configuration': instance.provider_configuration,
            'state': None,
            'public_ips': [],
            'private_ips': [],
        }

        compute_instance = ComputeInstance.objects.create(**compute_instance_args)
        print('Recreated instance %s for provider_size %s' % (compute_instance.pk, instance.provider_size))


@app.task()
def create_libcloud_node(compute_instance_id):
    from .models import ComputeInstance, PasswordAuthenticationMethod

    compute_instance = ComputeInstance.objects.get(pk=compute_instance_id)
    authentication_method = compute_instance.group.authentication_method
    provider_configuration = compute_instance.provider_configuration
    provider_size = compute_instance.provider_size

    if isinstance(authentication_method, PasswordAuthenticationMethod):
        libcloud_auth = NodeAuthPassword(authentication_method.password)
    else:
        libcloud_auth = NodeAuthSSHKey(authentication_method.key)

    libcloud_size = provider_size.to_libcloud_size()
    libcloud_image = compute_instance.provider_image.to_libcloud_image(provider_configuration)

    print('Creating libcloud node for instance %s, size %s' % (compute_instance.pk, provider_size))
    libcloud_node_args = {
        'name': compute_instance.name,
        'libcloud_image': libcloud_image,
        'libcloud_size': libcloud_size,
        'libcloud_auth': libcloud_auth,
    }
    libcloud_node = provider_configuration.create_libcloud_node(**libcloud_node_args)

    print('Done creating libcloud node for instance %s, size %s' % (compute_instance.pk, provider_size))
    compute_instance.external_id = libcloud_node.id
    compute_instance.public_ips = json.loads(json.dumps(libcloud_node.public_ips))
    compute_instance.private_ips = json.loads(json.dumps(libcloud_node.private_ips))
    compute_instance.extra = json.loads(json.dumps(libcloud_node.extra, cls=NodeJSONEncoder))
    compute_instance.save()