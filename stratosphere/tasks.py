from celery.task.schedules import crontab
from celery.decorators import periodic_task

from datetime import datetime, timedelta

from django.db import connection, OperationalError, transaction

from libcloud.compute.base import Node, NodeAuthPassword, NodeAuthSSHKey

import json

from multicloud.celery import app

import random
import string

from .util import BackoffError, NodeJSONEncoder

# we don't import import models here, since doing so seems to screw up bootstrapping


@app.task()
def load_available_images(provider_configuration_id):
    from .models import ProviderConfiguration

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)
    provider_configuration.load_available_images()


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
        check_instance_distribution.delay(compute_group_id)


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
        update_instance_statuses.delay(provider_configuration_id)


@app.task()
def create_compute_instance(provider_configuration_id, provider_size_id, authentication_method_id,
                            compute_group_id):
    from .models import AuthenticationMethod, ComputeGroup, ComputeInstance, PasswordAuthenticationMethod, \
                        ProviderConfiguration, ProviderImage, ProviderSize

    compute_group = ComputeGroup.objects.get(pk=compute_group_id)
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_configuration_id)

    # filter on provider as well, since available_provider_images could contain shared images
    # TODO wait, does that make sense?
    # TODO could this also produce multiple images if we don't specify the provider size?
    provider_image = provider_configuration.available_provider_images.get(
                            disk_image__disk_image_mappings__operating_system_image=compute_group.image,
                            disk_image__disk_image_mappings__provider=provider_configuration.provider)

    provider_size = ProviderSize.objects.get(pk=provider_size_id)
    authentication_method = AuthenticationMethod.objects.get(pk=authentication_method_id)

    name_suffix = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    name = '%s-%s' % (compute_group.name, name_suffix)

    compute_instance_args = {
        'name': name,
        'provider_image': provider_image,
        'group': compute_group,
        'provider_size': provider_size,
        'extra': {},
        'provider_configuration': provider_configuration,
        'state': None,
        'public_ips': [],
        'private_ips': [],
        'last_request_start_time': datetime.now(),
    }

    def create_libcloud_instance():
        if isinstance(authentication_method, PasswordAuthenticationMethod):
            libcloud_auth = NodeAuthPassword(authentication_method.password)
        else:
            libcloud_auth = NodeAuthSSHKey(authentication_method.key)

        libcloud_size = provider_size.to_libcloud_size()
        libcloud_image = provider_image.to_libcloud_image(provider_configuration)

        print('creating libcloud node for instance %d, size %s' % (compute_instance.pk, provider_size))
        libcloud_node = provider_configuration.create_libcloud_node(name=name, libcloud_image=libcloud_image,
                                                                    libcloud_size=libcloud_size, libcloud_auth=libcloud_auth)

        print('done creating libcloud node for instance %d, size %s' % (compute_instance.pk, provider_size))
        compute_instance.state = ComputeInstance.PENDING
        compute_instance.external_id = libcloud_node.id
        compute_instance.public_ips = json.loads(json.dumps(libcloud_node.public_ips))
        compute_instance.private_ips = json.loads(json.dumps(libcloud_node.private_ips))
        compute_instance.extra = json.loads(json.dumps(libcloud_node.extra, cls=NodeJSONEncoder))
        compute_instance.save()

    with transaction.atomic():
        intended_instance_count = compute_group.size_distribution[str(provider_size.pk)]
        current_instance_count = compute_group.pending_or_running_count(provider_size)

        print('size_distribution: %s' % compute_group.size_distribution)
        print('%s: current_instance_count < intended_instance_count = %d < %d = %s' %
              (provider_size, current_instance_count, intended_instance_count,
               current_instance_count < intended_instance_count))

        if current_instance_count < intended_instance_count:
            compute_instance = ComputeInstance.objects.create(**compute_instance_args)
            print('created instance %d for provider_size %s' % (compute_instance.pk, provider_size))
            connection.on_commit(create_libcloud_instance)