from django.forms import modelform_factory
from django.http import HttpResponse, JsonResponse
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

    operating_system_images = OperatingSystemImage.objects.filter(
                                        disk_images__provider_images__provider_configuration__user_configuration__user=request.user)

    os_images_map = {os_image: ProviderConfiguration.objects.filter(user_configuration__user=request.user,
                                        provider_images__disk_image__operating_system_images=os_image)
                     for os_image in operating_system_images}

    providers = ProviderConfiguration.objects.all()

    possible_providers = [
        {
            'name': 'aws',
            'available': True,
            'image_top_margin': '25px',
        },
        {
            'name': 'linode',
            'available': True,
            'image_top_margin': '12px',
        },
        {
            'name': 'azure',
            'available': False,
            'image_top_margin': '15px',
        },
        {
            'name': 'digitalocean',
            'available': False,
            'image_top_margin': '0',
        },
        {
            'name': 'softlayer',
            'available': False,
            'image_top_margin': '0',
        },
        {
            'name': 'cloudsigma',
            'available': False,
            'image_top_margin': '0',
        },
        {
            'name': 'google',
            'available': False,
            'image_top_margin': '0',
        },
    ]

    context = {
        'os_images_map': os_images_map,
        'providers': providers,
        'possible_providers': possible_providers,
    }
    return render(request, 'stratosphere/index.html', context=context)


def _compute_group_to_json(group):
    return {'id': group.id, 'name': group.name, 'cpu': group.cpu, 'memory': group.memory,
            'instance_count': group.instance_count, 'providers': group.provider_states(),
            'state': group.state}


@basicauth
def compute(request, group_id=None):
    if request.method == 'GET':
        compute_groups = [_compute_group_to_json(group) for group in ComputeGroup.objects.all()]

        return JsonResponse(compute_groups, safe=False)

    elif request.method == 'DELETE':
        group = ComputeGroup.objects.get(pk=group_id)
        group.terminate()
        return HttpResponse('')

    elif request.method == 'POST':
        params = json.loads(request.body.decode('utf-8'))
        print('params', params)
        cpu = int(params['cpu'])
        memory = int(params['memory'])
        instance_count = int(params['instance_count'])
        name = params['name']

        provider_policy = {}
        for key in params:
            match = re.match(r'provider_choice_(.+)', key)
            if match is not None:
                provider_name = match.group(1)
                provider_policy[provider_name] = 'auto'

        provider_policy_str = json.dumps(provider_policy)

        if params['deployment_type'] == 'os':
            os_id = params['operating_system']
            operating_system_image = OperatingSystemImage.objects.get(pk=os_id)
            group = OperatingSystemComputeGroup.objects.create(user_configuration=request.user.configuration, cpu=cpu, memory=memory,
                                                               instance_count=instance_count, name=name, provider_policy=provider_policy_str,
                                                               image=operating_system_image)

        group.create_instances()

        return JsonResponse(_compute_group_to_json(group))


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


@basicauth
def provider_action(request, provider_name, action):
    provider_configuration = ProviderConfiguration.objects.get(provider_name=provider_name)

    if action == 'restore':
        provider_configuration.simulate_restore()
    elif action == 'fail':
        provider_configuration.simulate_failure()
    else:
        return HttpResponse(status=422)

    return HttpResponse('')
