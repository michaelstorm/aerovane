from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.forms import modelform_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

import base64
import json
import re

from .forms import *
from .tasks import load_provider_data
from .util import schedule_random_default_delay, unix_time_millis


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
                                                           disk_image_mappings__compute_image=os).first()

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
        operating_systems = ComputeImage.objects.all()
        operating_systems_json = [operating_system_to_json(os) for os in operating_systems]

        return JsonResponse(operating_systems_json, safe=False)


    elif request.method == 'POST':
        params = json.loads(request.body.decode('utf-8'))
        os_id = params.get('id')

        if os_id is None:
            operating_system = ComputeImage.objects.create(name=params['name'], user=request.user)
        else:
            operating_system = ComputeImage.objects.get(pk=os_id)

        operating_system.name = params['name']

        operating_system.disk_image_mappings.all().delete()

        for provider_json in params['providers']:
            provider_configuration = ProviderConfiguration.objects.get(pk=provider_json['id'])

            disk_image_json = provider_json.get('disk_image')
            if isinstance(disk_image_json, dict): # Angular sometimes sends null value as empty string
                new_disk_image = DiskImage.objects.get(pk=disk_image_json['id'])
                DiskImageMapping.objects.get_or_create(provider=provider_configuration.provider,
                                disk_image=new_disk_image, compute_image=operating_system)

        operating_system.save()

        return JsonResponse(operating_system_to_json(operating_system))


@login_required
def images(request):
    operating_systems = ComputeImage.objects.all()

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
def compute_group(request, group_id):
    context = {
        # 'compute_group_id': group_id,
        'left_nav_section': 'dashboard',
        'left_sub_nav_section': 'view',
    }

    return render(request, 'stratosphere/compute_group.html', context=context)


@login_required
def add_compute_group(request):
    compute_images = ComputeImage.objects.filter(user=request.user)

    os_images_map = {os_image: Provider.objects.filter(
                            provider_images__disk_image__disk_image_mappings__compute_image=os_image).distinct()
                     for os_image in compute_images}

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
            'available': False,
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


def _provider_size_to_json(size):
    return {'id': size.pk, 'external_id': size.external_id,
            'name': size.name, 'price': size.price, 'memory': size.ram,
            'disk': size.disk, 'bandwidth': size.bandwidth, 'cpu': size.cpu}


def _compute_instance_to_json(instance):
    # TODO do we explicitly handle the states that are not enumerated here?
    if instance.is_running():
        display_state = 'running'
    elif instance.is_pending():
        display_state = 'pending'
    elif instance.is_destroyed():
        display_state = 'destroyed'
    elif instance.is_failed():
        display_state = 'failed'

    destroyed_at = instance.destroyed_at.timestamp() if instance.destroyed_at is not None else None
    failed_at = instance.failed_at.timestamp() if instance.failed_at is not None else None

    provider_size_json = _provider_size_to_json(instance.provider_size)

    return {'id': instance.pk, 'provider_size': provider_size_json,
            'provider_pretty_name': instance.provider_configuration.provider.pretty_name,
            'name': instance.name, 'created_at': instance.created_at.timestamp(),
            'external_id': instance.external_id, 'public_ips': instance.public_ips,
            'private_ips': instance.private_ips, 'destroyed_at': destroyed_at,
            'failed_at': failed_at, 'state': instance.state,
            'display_state': display_state}


def _compute_group_to_json(group):
    state = group.instances.filter(~Q(state=ComputeInstance.TERMINATED))
    instances_json = [_compute_instance_to_json(instance) for instance in state]
    return {'id': group.pk, 'name': group.name, 'cpu': group.cpu, 'memory': group.memory,
            'running_instance_count': group.instances.filter(ComputeInstance.running_instances_query()).count(),
            'instance_count': group.instance_count, 'providers': group.provider_states(),
            'state': group.state, 'instances': instances_json, 'created_at': group.created_at.timestamp()}


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

    return redirect('/authentication/')


@login_required
def compute(request, group_id=None):
    if request.method == 'GET':
        if group_id is None:
            compute_groups = [_compute_group_to_json(group) for group in ComputeGroup.objects.all()]
            return JsonResponse(compute_groups, safe=False)
        else:
            compute_group = _compute_group_to_json(request.user.configuration.compute_groups.filter(pk=group_id).first())
            # return an array because I can't figure out how to get Angular to not expect one
            return JsonResponse([compute_group], safe=False)

    elif request.method == 'DELETE':
        group = ComputeGroup.objects.get(pk=group_id)
        group.destroy()
        return HttpResponse('')

    elif request.method == 'POST':
        params = json.loads(request.body.decode('utf-8'))
        cpu = int(params['cpu'])
        memory = int(params['memory'])
        instance_count = int(params['instance_count'])
        name = params['name']

        authentication_method_id = params['authentication_method']
        authentication_method = request.user.configuration.authentication_methods.filter(pk=authentication_method_id).first()

        provider_policy = {}
        for key in params:
            match = re.match(r'provider_choice_(.+)', key)
            if match is not None:
                provider_name = match.group(1)
                provider_policy[provider_name] = 'auto'

        os_id = params['operating_system']
        compute_image = ComputeImage.objects.get(pk=os_id)
        group = ComputeGroup.objects.create(user_configuration=request.user.configuration, cpu=cpu, memory=memory,
                                            instance_count=instance_count, name=name, provider_policy=provider_policy,
                                            size_distribution={}, image=compute_image,
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
def configure_provider(request, provider_name):
    context = {}

    if provider_name == 'aws':
        provider_configuration = request.user.configuration.provider_configurations.instance_of(Ec2ProviderConfiguration).first()
        if provider_configuration is None:
            Ec2ProviderConfiguration.create_regions(request.user,
                            request.POST['aws_access_key_id'], request.POST['aws_secret_access_key'])

        else:
            credentials = provider_configuration.credentials
            credentials.access_key_id = request.POST['aws_access_key_id']
            credentials.secret_access_key = request.POST['aws_secret_access_key']
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

    return redirect('/providers/')


@login_required
def providers_loaded(request):
    user = User.objects.get(pk=request.user.pk)
    loaded = True
    for provider_configuration in user.configuration.provider_configurations.all():
        if not provider_configuration.loaded:
            loaded = False
            break

    return JsonResponse({'loaded': loaded})


@login_required
def providers_refresh(request):
    provider_configurations = request.user.configuration.provider_configurations.all()

    for provider_configuration in provider_configurations:
        provider_configuration.loaded = False
        provider_configuration.save()

        schedule_random_default_delay(load_provider_data, provider_configuration.pk)

    return HttpResponse('')


def _provider_json(provider_configuration):
    return {'id': provider_configuration.pk,
            'pretty_name': provider_configuration.provider.pretty_name,
            'enabled': provider_configuration.enabled,
            'failure_count': provider_configuration.failure_count(timezone.now()),
            'max_failure_count': provider_configuration.max_failure_count(),
            'total_instances': provider_configuration.instances.filter(~ComputeInstance.unavailable_instances_query()).count()}


@login_required
def get_providers(request, provider_id=None):
    if 'text/html' in request.META.get('HTTP_ACCEPT'):
        provider_configurations = request.user.configuration.provider_configurations
        context = {key: form_class(instance=provider_configurations.filter(provider_name=key).first())
                   for key, form_class in provider_configuration_form_classes.items()}

        context['left_nav_section'] = 'providers'

        aws_credentials = Ec2ProviderCredentials.objects.first()
        if aws_credentials is not None:
            context['aws_access_key_id'] = aws_credentials.access_key_id

        return render(request, 'stratosphere/providers.html', context=context)

    elif provider_id is None:
        provider_configurations = request.user.configuration.provider_configurations.all()
        return JsonResponse([_provider_json(pc) for pc in provider_configurations], safe=False)

    else:
        provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)
        return JsonResponse(_provider_json(provider_configuration))


@login_required
def set_provider_enabled(request, provider_id):
    params = json.loads(request.body.decode('utf-8'))
    enabled = params['enabled']

    provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)
    provider_configuration.set_enabled(enabled)

    return HttpResponse('')


@login_required
def provider_disk_images(request, provider_id):
    query = request.GET.get('query')
    provider_configuration = ProviderConfiguration.objects.get(pk=provider_id)

    terms = [t for t in re.split(r'\s+', query) if len(t) > 0]
    if len(terms) > 0:
        f = Q()
        for term in terms:
            f = f & (Q(name__icontains=term) | Q(provider_images__external_id__icontains=term))

        disk_images = provider_configuration.available_disk_images.filter(f)

        disk_images_json = [_disk_image_to_json(d) for d in disk_images[:10]]
        return JsonResponse(disk_images_json, safe=False)
    else:
        return JsonResponse([], safe=False)


@login_required
def state_history(request, group_id=None):
    def get_history_dict(h):
        return {'time': unix_time_millis(h[0]),
                'running': h[1].running,
                'pending': h[1].pending,
                'failed': h[1].failed}

    time_field = 'time' if group_id is None else 'user_snapshot__time'

    limit = request.GET.get('limit')
    if limit is None or len(limit.strip()) == 0:
        limit_datetime = None
        limit_query = Q()
    else:
        limit_datetime = timezone.now() - timedelta(seconds=int(limit))
        limit_query = Q(**{'%s__gte' % time_field: limit_datetime})

    if group_id is None:
        snapshots = request.user.configuration.instance_states_snapshots
    else:
        group = request.user.configuration.compute_groups.filter(pk=group_id).first()
        snapshots = GroupInstanceStatesSnapshot.objects.filter(group=group)

    snapshots = snapshots.order_by(time_field)

    if group_id is None:
        history = [(s.time, s) for s in snapshots.filter(limit_query)]
    else:
        # TODO optimize this with a JOIN
        history = [(s.user_snapshot.time, s) for s in snapshots.filter(limit_query)]

    if len(history) == 0:
        last_snapshot = snapshots.last()
        if last_snapshot is not None:
            time = last_snapshot.time if group_id is None else last_snapshot.user_snapshot.time
            history = [(time, last_snapshot)]
    elif limit_datetime is not None:
        previous_snapshot = snapshots.filter(**{'%s__lt' % time_field: limit_datetime}).last()

        if previous_snapshot is not None:
            history = [(limit_datetime, previous_snapshot)] + history

    history = [get_history_dict(h) for h in history]
    return JsonResponse(history, safe=False)