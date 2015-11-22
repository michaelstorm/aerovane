from django.forms import modelform_factory
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import View

import base64
import json
import re

from .forms import *


def view_or_basicauth(view, request, *args, **kwargs):
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2:
            if auth[0].lower() == "basic":
                decoded_auth = base64.b64decode(auth[1]).decode('utf-8')
                uname, passwd = decoded_auth.split(':')
                if uname == 'admin' and passwd == 'stratosphere777':
                    return view(request, *args, **kwargs)

    response = HttpResponse()
    response.status_code = 401
    response['WWW-Authenticate'] = 'Basic realm="stratosphere"'
    return response


def basicauth(view_func):
    def wrapper(request, *args, **kwargs):
        return view_or_basicauth(view_func, request, *args, **kwargs)
    return wrapper


def robots(request):
    return render(request, 'robots.txt', content_type='text/plain')


@basicauth
def index(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    compute_groups = ComputeGroup.objects.all()
    compute_groups_map = []

    for compute_group in compute_groups:
        group = {}
        group['group'] = compute_group

        providers = compute_group.provider_states()
        group['providers'] = providers

        compute_groups_map.append(group)

    operating_system_images = OperatingSystemImage.objects.filter(
                                        disk_images__provider_images__provider_configuration__user_configuration__user=request.user)

    os_images_map = {os_image: ProviderConfiguration.objects.filter(user_configuration__user=request.user,
                                        provider_images__disk_image__operating_system_images=os_image)
                     for os_image in operating_system_images}

    context = {
        'compute_groups_map': compute_groups_map,
        'os_images_map': os_images_map,
    }
    return render(request, 'stratosphere/index.html', context=context)


@basicauth
def compute(request):
    if request.method == 'POST':
        cpu = int(request.POST['cpu'])
        memory = int(request.POST['memory'])
        instance_count = int(request.POST['instance_count'])
        name = request.POST['name']

        provider_policy = {}
        for key in request.POST:
            match = re.match(r'provider-(.+)', key)
            if match is not None:
                provider_name = match.group(1)
                provider_policy[provider_name] = 'auto'

        provider_policy_str = json.dumps(provider_policy)

        if request.POST['deployment_type'] == 'os':
            print(request.POST)
            os_id = request.POST['operating_system']
            operating_system_image = OperatingSystemImage.objects.get(pk=os_id)
            group = OperatingSystemComputeGroup.objects.create(user_configuration=request.user.configuration, cpu=cpu, memory=memory,
                                                               instance_count=instance_count, name=name, provider_policy=provider_policy_str,
                                                               image=operating_system_image)

        group.create_instances()

        return redirect('/')


@basicauth
def sync(request):
    remote_instances = []

    for provider in settings.CLOUD_PROVIDERS.values():
        remote_instances.extend(provider.list_nodes())

    print(remote_instances)

        # orphan_local_instances = Ec2ComputeInstance.objects.exclude(external_id__in=[instance.id for instance in ec2_instances])
        # orphan_local_instances.delete()

        # live_remote_instances = filter(lambda instance: instance.state not in ['shutting-down', 'terminated'], ec2_instances)
        # orphan_remote_instances = [ec2_instance.id for ec2_instance in live_remote_instances
        #                            if len(Ec2ComputeInstance.objects.filter(external_id=ec2_instance.id)) > 0]
        # self._terminate_instances(orphan_remote_instances)

    return redirect('/')


@basicauth
def check_configure(request):
    provider_configurations = request.user.configuration.provider_configurations
    if len(provider_configurations.all()) == 0:
        return redirect('/settings')
    else:
        return redirect('/')


provider_configuration_form_classes = {
    'aws': Ec2ProviderConfigurationForm,
    'linode': LinodeProviderConfigurationForm,
}


@basicauth
def settings(request):
    provider_configurations = request.user.configuration.provider_configurations
    print('instances:', [provider_configurations.filter(provider_name=key).first() for key in provider_configuration_form_classes])
    context = {key: form_class(instance=provider_configurations.filter(provider_name=key).first())
               for key, form_class in provider_configuration_form_classes.items()}
    # context['aws_images'] = DiskImage.objects.filter(provider_images__provider_name='aws')
    # context['aws_default_ubuntu_14_04_image'] = 'ami-df6a8b9b'
    return render(request, 'stratosphere/settings.html', context=context)


@basicauth
def configure_provider(request, provider_name):
    context = {}
    for key, form_class in provider_configuration_form_classes.items():
        if key == provider_name:
            provider_form = form_class(request.POST)
            provider_configuration = provider_form.save()
            provider_configuration.provider_name = key
            provider_configuration.user_configuration = request.user.configuration
            provider_configuration.save()
            context[key] = provider_form
        else:
            context[key] = form_class()

    return render(request, 'stratosphere/settings.html', context=context)
