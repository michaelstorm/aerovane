from django.contrib.auth.decorators import login_required
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
            selected_disk_image = DiskImage.objects.filter(disk_image_mappings__provider=provider_configuration.provider,
                                                           disk_image_mappings__operating_system_image=os).first()

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

        operating_system.disk_image_mappings.all().delete()

        for provider_json in params['providers']:
            print('provider_json:', provider_json)
            provider_configuration = ProviderConfiguration.objects.get(pk=provider_json['id'])

            disk_image_json = provider_json.get('disk_image')
            if isinstance(disk_image_json, dict): # Angular sometimes sends null value as empty string
                new_disk_image = DiskImage.objects.get(pk=disk_image_json['id'])
                print('Adding disk image %d' % new_disk_image.pk)
                DiskImageMapping.objects.get_or_create(provider=provider_configuration.provider,
                                disk_image=new_disk_image, operating_system_image=operating_system)

        operating_system.save()

        return JsonResponse(operating_system_to_json(operating_system))


@login_required
def images(request):
    operating_systems = OperatingSystemImage.objects.all()

    context = {
        'left_nav_section': 'images',
        'operating_systems': operating_systems,
        'providers': request.user.configuration.provider_configurations.all(),
    }

    return render(request, 'stratosphere/images.html', context=context)


@login_required
def compute_groups(request):
    context = {
        'providers': ProviderConfiguration.objects.all(),
        'left_nav_section': 'dashboard',
        'left_sub_nav_section': 'view',
    }

    return render(request, 'stratosphere/compute_groups.html', context=context)


@login_required
def add_compute_group(request):
    operating_system_images = OperatingSystemImage.objects.filter(user=request.user)

    os_images_map = {os_image: Provider.objects.filter(
                            provider_images__disk_image__disk_image_mappings__operating_system_image=os_image).distinct()
                     for os_image in operating_system_images}

    possible_providers = [
        {
            'name': 'aws_us_east_1',
            'available': True,
        },
        {
            'name': 'aws_us_west_1',
            'available': True,
        },
        {
            'name': 'aws_us_west_2',
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


@login_required
def authentication(request):
    context = {
        'key_methods': KeyAuthenticationMethod.objects.all(),
        'password_methods': PasswordAuthenticationMethod.objects.all(),
        'add_key_method': KeyAuthenticationMethodForm(),
        'add_password_method': PasswordAuthenticationMethodForm(),
        'left_nav_section': 'authentication',
    }

    return render(request, 'stratosphere/authentication.html', context=context)


@login_required
def authentication_methods(request, method_id=None):
    if request.method == 'POST':
        if 'key' in request.POST:
            KeyAuthenticationMethod.objects.create(user_configuration=request.user.configuration,
                name=request.POST['name'], key=request.POST['key'])
        else:
            PasswordAuthenticationMethod.objects.create(user_configuration=request.user.configuration,
                name=request.POST['name'], password=request.POST['password'])

    elif request.method == 'DELETE':
        AuthenticationMethod.objects.filter(id=method_id).delete()

    return redirect('/providers/')


@login_required
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

        if params['deployment_type'] == 'os':
            os_id = params['operating_system']
            operating_system_image = OperatingSystemImage.objects.get(pk=os_id)
            group = OperatingSystemComputeGroup.objects.create(user_configuration=request.user.configuration, cpu=cpu, memory=memory,
                                                               instance_count=instance_count, name=name, provider_policy=provider_policy,
                                                               size_distribution={}, image=operating_system_image,
                                                               authentication_method=authentication_method)

        group.rebalance_instances()

        return JsonResponse(_compute_group_to_json(group))


@login_required
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


@login_required
def providers(request):
    provider_configurations = request.user.configuration.provider_configurations
    context = {key: form_class(instance=provider_configurations.filter(provider_name=key).first())
               for key, form_class in provider_configuration_form_classes.items()}

    context['left_nav_section'] = 'providers'

    return render(request, 'stratosphere/providers.html', context=context)


@login_required
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


@login_required
def provider_action(request, provider_id, action):
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)

    if action == 'restore':
        provider_configuration.simulate_restore()
    elif action == 'fail':
        provider_configuration.simulate_failure()
    else:
        return HttpResponse(status=422)

    return HttpResponse('')


@login_required
def provider_disk_images(request, provider_id):
    query = request.GET.get('query')
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)

    terms = [t for t in re.split(r'\s+', query) if len(t) > 0]
    print('terms', terms)
    if len(terms) > 0:
        f = Q()
        for term in terms:
            f = f & (Q(name__icontains=term) | Q(provider_images__image_id__icontains=term))
        print(f)
        disk_images = provider_configuration.available_disk_images.filter(f)

        disk_images_json = [_disk_image_to_json(d) for d in disk_images[:10]]
        return JsonResponse(disk_images_json, safe=False)
    else:
        return JsonResponse([], safe=False)
