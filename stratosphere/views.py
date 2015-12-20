from django.db.models import Q
from django.forms import modelform_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

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


def _disk_image_to_json(d):
    if d is None:
        return None
    else:
        return {
            'id': d.pk,
            'name': d.name,
        }


def operating_systems(request):
    def operating_system_to_json(os):
        def provider_to_json(provider_configuration):
            disk_images = DiskImage.objects.filter(provider_images__provider=provider_configuration.provider)
            selected_disk_image = disk_images.filter(operating_system_images=os).first()

            return {
                'id': provider_configuration.pk,
                'pretty_name': provider_configuration.provider.pretty_name,
                'disk_image': _disk_image_to_json(selected_disk_image),
            }

        provider_configurations = request.user.configuration.provider_configurations.all()

        return {
            'id': os.pk,
            'name': os.name,
            'providers': [provider_to_json(p) for p in provider_configurations],
        }

    if request.method == 'GET':
        operating_systems = OperatingSystemImage.objects.all()
        operating_systems_json = [operating_system_to_json(os) for os in operating_systems]

        return JsonResponse(operating_systems_json, safe=False)


    elif request.method == 'POST':
        params = json.loads(request.body.decode('utf-8'))
        os_id = params.get('id')

        if os_id is None:
            operating_system = OperatingSystemImage.objects.create(name=params['name'], user=request.user)
        else:
            operating_system = OperatingSystemImage.objects.get(pk=os_id)

        operating_system.name = params['name']

        for provider_json in params['providers']:
            provider_configuration = ProviderConfiguration.objects.get(pk=provider_json['id'])

            existing_disk_image = operating_system.disk_images.filter(provider_images__provider=provider_configuration.provider).first()
            if existing_disk_image is not None:
                print('Removing disk image %d from operating system image %d' % (existing_disk_image.pk, operating_system.pk))
                operating_system.disk_images.remove(existing_disk_image)

            if provider_json.get('disk_image') is not None:
                new_disk_image = DiskImage.objects.get(pk=provider_json['disk_image']['id'])
                print('Adding disk image %d' % new_disk_image.pk)
                operating_system.disk_images.add(new_disk_image)

        operating_system.save()

        return JsonResponse(operating_system_to_json(operating_system))


def images(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    operating_systems = OperatingSystemImage.objects.all()

    context = {
        'left_nav_section': 'images',
        'operating_systems': operating_systems,
        'providers': request.user.configuration.provider_configurations.all(),
    }

    return render(request, 'stratosphere/images.html', context=context)


@basicauth
def compute_groups(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    context = {
        'providers': ProviderConfiguration.objects.all(),
        'left_nav_section': 'dashboard',
        'left_sub_nav_section': 'view',
    }

    return render(request, 'stratosphere/compute_groups.html', context=context)


@basicauth
def add_compute_group(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    operating_system_images = OperatingSystemImage.objects.filter(user=request.user)

    os_images_map = {os_image: ProviderConfiguration.objects.filter(user_configuration__user=request.user,
                                        provider_images__disk_image__operating_system_images=os_image)
                     for os_image in operating_system_images}

    possible_providers = [
        {
            'name': 'aws',
            'available': True,
        },
        {
            'name': 'linode',
            'available': True,
        },
        {
            'name': 'azure',
            'available': False,
        },
        {
            'name': 'digitalocean',
            'available': False,
        },
        {
            'name': 'softlayer',
            'available': False,
        },
        {
            'name': 'cloudsigma',
            'available': False,
        },
        {
            'name': 'google',
            'available': False,
        },
    ]

    context = {
        'os_images_map': os_images_map,
        'possible_providers': possible_providers,
        'authentication_methods': AuthenticationMethod.objects.all(),
        'left_nav_section': 'dashboard',
        'left_sub_nav_section': 'add',
    }
    return render(request, 'stratosphere/add_compute_group.html', context=context)


def _compute_group_to_json(group):
    return {'id': group.id, 'name': group.name, 'cpu': group.cpu, 'memory': group.memory,
            'instance_count': group.instance_count, 'providers': group.provider_states(),
            'state': group.state}


@basicauth
def authentication(request):
    context = {
        'key_methods': KeyAuthenticationMethod.objects.all(),
        'password_methods': PasswordAuthenticationMethod.objects.all(),
        'add_key_method': KeyAuthenticationMethodForm(),
        'add_password_method': PasswordAuthenticationMethodForm(),
        'left_nav_section': 'authentication',
    }

    return render(request, 'stratosphere/authentication.html', context=context)


@basicauth
def authentication_methods(request, method_id=None):
    if request.method == 'POST':
        if 'key' in request.POST:
            form = KeyAuthenticationMethodForm(request.POST)
        else:
            form = PasswordAuthenticationMethodForm(request.POST)

        method = form.save()

        method.user_configuration = request.user.configuration
        method.save()

    elif request.method == 'DELETE':
        AuthenticationMethod.objects.filter(id=method_id).delete()

    return redirect('/providers/')


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
        cpu = int(params['cpu'])
        memory = int(params['memory'])
        instance_count = int(params['instance_count'])
        name = params['name']

        authentication_method_id = params['authentication_method']
        authentication_method = AuthenticationMethod.objects.get(pk=authentication_method_id)

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
                                                               image=operating_system_image, authentication_method=authentication_method)

        group.create_instances()

        return JsonResponse(_compute_group_to_json(group))


@basicauth
def check_configure(request):
    provider_configurations = request.user.configuration.provider_configurations
    if len(provider_configurations.all()) == 0:
        return redirect('/providers/')
    else:
        return redirect('/')


provider_configuration_form_classes = {
    'aws': Ec2ProviderConfigurationForm,
    'linode': LinodeProviderConfigurationForm,
}


def providers(request):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    provider_configurations = request.user.configuration.provider_configurations
    context = {key: form_class(instance=provider_configurations.filter(provider_name=key).first())
               for key, form_class in provider_configuration_form_classes.items()}

    context['left_nav_section'] = 'providers'

    return render(request, 'stratosphere/providers.html', context=context)


@basicauth
def configure_provider(request, provider_name):
    context = {}

    if provider_name == 'aws':
        provider_configuration = request.user.configuration.provider_configurations.instance_of(Ec2ProviderConfiguration).first()
        if provider_configuration is None:
            Ec2ProviderConfiguration.create_regions(request.user,
                            request.POST['aws_access_key_id'], request.POST['secret_access_key'])

        else:
            credentials = provider_configuration.credentials
            credentials.access_key_id = request.POST['aws_access_key_id']
            credentials.secret_access_key = request.POST['secret_access_key']
            credentials.save()

    else:
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

    return render(request, 'stratosphere/providers.html', context=context)


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


def provider_disk_images(request, provider_id):
    if not request.user.is_authenticated():
        return redirect('/accounts/login/')

    query = request.GET.get('query')
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)

    disk_images = DiskImage.objects.filter(
                      Q(provider_images__provider_configuration=provider_configuration)
                    | (Q(provider_images__provider_configuration=None)
                       & Q(provider_images__provider=provider_configuration.provider)))

    result_disk_images = disk_images.filter(
                      Q(name__icontains=query)
                    | Q(provider_images__image_id__icontains=query))

    disk_images_json = [_disk_image_to_json(d) for d in result_disk_images[:10]]
    return JsonResponse(disk_images_json, safe=False)