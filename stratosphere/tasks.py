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

from .util import BackoffError, NodeJSONEncoder, schedule_random_default_delay

# we don't import import models here, since doing so seems to screw up bootstrapping


@app.task()
def load_available_images(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.load_available_images()


@app.task()
def check_instance_states_snapshots(user_configuration_id):
    from .models import UserConfiguration

    def snapshots_values(snapshot):
        return {x: y for x, y in last_user_snapshot.__dict__.items()
                if not x.startswith('_') and x != 'time' and x != 'id'}

    def snapshot_values_equal(first, second):
        if first is None or second is None:
            return first is None and second is None
        else:
            return snapshots_values(first) == snapshots_values(second)

    user_configuration = UserConfiguration.objects.get(pk=user_configuration_id)

    user_snapshot, group_snapshots = user_configuration.create_phantom_instance_states_snapshot()
    last_user_snapshot = user_configuration.instance_states_snapshots.order_by('-time').first()

    not_equal = snapshot_values_equal(user_snapshot, last_user_snapshot)

    if not not_equal and last_user_snapshot is not None:
        group_snapshots_map = {group.pk: group for group in last_user_snapshot.group_snapshots.all()}
        last_group_snapshots_map = {group.pk: group for group in last_user_snapshot.group_snapshots.all()}

        all_group_ids = [list(group_snapshots_map.keys()) + list(last_group_snapshots_map.key())]
        for group_id in all_group_ids:
            if not snapshot_values_equal(group_snapshots_map[group_id], last_group_snapshots_map[group_id]):
                not_equal = True
                break

    if not_equal:
        with transaction.atomic():
            user_snapshot.save()

            for group_snapshot in group_snapshots:
                group_snapshot.user_snapshot = user_snapshot
                group_snapshot.save()


@periodic_task(run_every=timedelta(seconds=30))
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


@periodic_task(run_every=timedelta(minutes=2))
def clean_up_terminated_instances():
    from .models import ComputeInstance

    two_minutes_ago = timezone.now() - timedelta(minutes=2)
    leftover_terminated_instances = ComputeInstance.objects.filter(
        Q(terminated=True, last_request_start_time__lte=two_minutes_ago)
        & ~Q(state=ComputeInstance.TERMINATED))

    for instance in leftover_terminated_instances:
        terminate_libcloud_node.delay(instance.pk)


@app.task()
def terminate_libcloud_node(compute_instance_id):
    from .models import ComputeInstance

    instance = ComputeInstance.objects.get(pk=compute_instance_id)

    if instance.external_id is None:
        print('No external_id for instance %d; not terminating libcloud node' % compute_instance.pk)
    else:
        instance.provider_configuration.destroy_libcloud_node(instance.to_libcloud_node())

    instance.state = ComputeInstance.TERMINATED
    instance.save()


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

    print('creating libcloud node for instance %d, size %s' % (compute_instance.pk, provider_size))
    libcloud_node_args = {
        'name': compute_instance.name,
        'libcloud_image': libcloud_image,
        'libcloud_size': libcloud_size,
        'libcloud_auth': libcloud_auth,
    }
    libcloud_node = provider_configuration.create_libcloud_node(**libcloud_node_args)

    print('done creating libcloud node for instance %d, size %s' % (compute_instance.pk, provider_size))
    compute_instance.state = ComputeInstance.PENDING
    compute_instance.external_id = libcloud_node.id
    compute_instance.public_ips = json.loads(json.dumps(libcloud_node.public_ips))
    compute_instance.private_ips = json.loads(json.dumps(libcloud_node.private_ips))
    compute_instance.extra = json.loads(json.dumps(libcloud_node.extra, cls=NodeJSONEncoder))
    compute_instance.save()