from celery.task.schedules import crontab
from celery.decorators import periodic_task

from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import connection, OperationalError, transaction
from django.db.models import Q
from django.template.loader import render_to_string
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
    if provider_configuration.provider_credential_set.error_type is None:
        provider_configuration.load_data(False)


@app.task()
def load_public_provider_data(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    if provider_configuration.provider_credential_set.error_type is None:
        provider_configuration.load_data(True)


@periodic_task(run_every=timedelta(minutes=10))
def load_provider_data_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.exclude(user=None).values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(load_provider_data, provider_configuration_id)


# There's no pagination for EC2 DescribeImages requests, which are what libcloud uses to query driver
# images. When querying public images, this loads about 40-70k driver images into memory. This is fine for
# one provider, but when a single worker queries multiple providers simultaneously, it can blow out memory on
# Heroku. So we send the tasks to a different queue that's processed by a worker with its concurrency set to
# 1.
@periodic_task(run_every=timedelta(minutes=10))
def load_public_provider_data_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.filter(user=None).values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        load_public_provider_data.apply_async(args=[provider_configuration_id], queue='load_public_provider_data')


@app.task()
def check_failed_instances(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    if provider_configuration.user is not None:
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
    if provider_configuration.user is not None:
        provider_configuration.check_enabled()


@periodic_task(run_every=timedelta(seconds=10))
def check_provider_enabled_all():
    from .models import ProviderConfiguration

    provider_configuration_ids = ProviderConfiguration.objects.all().values_list('pk', flat=True)
    for provider_configuration_id in provider_configuration_ids:
        schedule_random_default_delay(check_provider_enabled, provider_configuration_id)


@app.task()
def check_instance_states_snapshots(user_id):
    user = get_user_model().objects.get(pk=user_id)
    user.take_instance_states_snapshot_if_changed()


@periodic_task(run_every=timedelta(seconds=15))
def check_instance_states_snapshots_all():
    user_ids = get_user_model().objects.all().values_list('pk', flat=True)
    for user_id in user_ids:
        check_instance_states_snapshots.delay(user_id)


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
    if provider_configuration.user is not None and provider_configuration.instances.count() > 0:
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

    libcloud_name = '%s_%s' % (compute_instance.group.name, compute_instance.name)
    libcloud_size = provider_size.to_libcloud_size()
    libcloud_image = compute_instance.provider_image.to_libcloud_image(provider_configuration)

    print('Creating libcloud node for instance %s, size %s' % (compute_instance.pk, provider_size))
    libcloud_node_args = {
        'name': libcloud_name,
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


@app.task()
def send_failed_email(provider_configuration_id):
    from .models import ComputeGroup, ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    compute_groups = ComputeGroup.objects.filter(instances__provider_configuration=provider_configuration).distinct()
    current_site = Site.objects.get_current()

    user_email = provider_configuration.user.email
    from_email = 'Aerovane <noreply@aerovane.io>'
    subject = 'Important message from Aerovane: Provider %s has FAILED' % provider_configuration.provider.pretty_name

    template_base_path = 'stratosphere/email/provider_failed'

    def migrated_instance_count(compute_group):
        return compute_group.instances.filter(provider_configuration=provider_configuration).count()

    groups_context = [{'pk': group.pk, 'name': group.name, 'migrated_instance_count': migrated_instance_count(group)} for group in compute_groups]

    template_context = {
        'provider_configuration': provider_configuration,
        'compute_groups': groups_context,
        'current_site': current_site,
    }

    message_plain = render_to_string('%s.txt' % template_base_path, template_context)
    message_html  = render_to_string('%s.html' % template_base_path, template_context)

    send_mail(subject, message_plain, from_email, [user_email], html_message=message_html, fail_silently=False)
