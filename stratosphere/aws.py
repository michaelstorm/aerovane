from django.db import OperationalError
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import json
import random
import re
import requests
import string
import threading

from .aws_api import *
from .models import *
from .util import *


request_lock = threading.Lock()


@retry(OperationalError)
def run_instances(request):
    args = {
        'image_id': request.POST.get('ImageId'),
        'min_count': request.POST.get('MinCount'),
        'max_count': request.POST.get('MaxCount'),
        'user_data': request.POST.get('UserData'),
        'instance_type': request.POST.get('InstanceType'),
        'instance_profile_name': request.POST.get('IamInstanceProfile.Name'),
        'placement': request.POST.get('Placement.AvailabilityZone'),
        'placement_group': request.POST.get('Placement.GroupName'),
        'monitoring_enabled': request.POST.get('Monitoring.Enabled') == 'true',
        'disable_api_termination': request.POST.get('DisableApiTermination') == 'true',
        'ebs_optimized': request.POST.get('EbsOptimized') == 'true',
    }

    authorization_header = request.META['HTTP_AUTHORIZATION']
    access_key_id = re.match(r'.*Credential=(.+?)/', authorization_header).group(1)
    provider_configuration = Ec2ProviderCredentials.objects.get(access_key_id=access_key_id).configurations.first()

    name_suffix = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    name = 'terraform-%s' % name_suffix

    provider_size = provider_configuration.provider_sizes.get(external_id=args['instance_type'])

    region = request.get_host().split('.')[1]
    image_id = args['image_id']

    if image_id.startswith('ami-'):
        provider_image = ProviderImage.objects.get(external_id=image_id)
    elif image_id.startswith('avmi-'):
        provider_name = 'aws_%s' % region.replace('-', '_')
        provider_image = ProviderImage.objects.get(
                            disk_image__disk_image_mappings__compute_image__pk=int(image_id[5:]),
                            provider__name=provider_name)
    else:
        raise Exception('Invalid image ID format')

    compute_image = provider_image.disk_image.disk_image_mappings.first().compute_image

    user_configuration = provider_configuration.user_configuration
    provider_policy = {pc.provider_name: 'auto' for pc
                                      in user_configuration.provider_configurations.all()}

    attributes = {
        'user_configuration': provider_configuration.user_configuration,
        'name': name,
        'cpu': int(provider_size.cpu),
        'memory': int(provider_size.ram),
        'instance_count': int(args['max_count']),
        'image': compute_image,
        'provider_policy': provider_policy,
        'size_distribution': {},
        'authentication_method': user_configuration.authentication_methods.instance_of(KeyAuthenticationMethod).first(),
    }

    compute_group = ComputeGroup.objects.filter(cpu=attributes['cpu'], memory=attributes['memory'],
                                                image=attributes['image']).first()

    compute_group = ComputeGroup.objects.create(**attributes)
    compute_group.rebalance_instances()

    instance_ids = ['avi-%d' % i for i in compute_group.instances.values_list('id', flat=True)]

    response_xml = run_instances_response(group_id=compute_group.pk, image_id=args['image_id'],
                                          instance_type=args['instance_type'], instance_ids=instance_ids)
    return HttpResponse(response_xml, 201)


def _get_instances_from_args(args):
    instances = {}

    for k in args.keys():
        if k.startswith('InstanceId.'):
            instance_id = args[k]

            if instance_id.startswith('i-'):
                instances[instance_id] = ComputeInstance.objects.get(external_id=instance_id)
            else:
                instances[instance_id] = ComputeInstance.objects.get(pk=instance_id[4:])

    return instances


def describe_instances(request):
    instances = _get_instances_from_args(request.POST)

    instance_id = list(instances.keys())[0]
    instance = instances[instance_id]

    # FIXME changes if instance is moved to a different provider
    instance_type = instance.provider_size.external_id

    image_id = 'avmi-%d' % instance.group.image.pk

    print('instance_id:', instance_id, 'instance:', instance)

    response_xml = describe_instances_response(group_id=instance.group.pk, image_id=image_id,
                                               instance_type=instance_type, instance_id=instance_id,
                                               state=instance.state)
    return HttpResponse(response_xml, 200)


def terminate_instances(request):
    instances = _get_instances_from_args(request.POST)

    instance_id = list(instances.keys())[0]
    instance = instances[instance_id]

    instance.group.terminate_instance(instance)

    response_xml = terminate_instances_response(instance_id=instance_id)
    return HttpResponse(response_xml, 200)


@csrf_exempt
def initial(request):
    with request_lock:
        host = request.get_host()
        action = request.POST['Action']

        print('XXX', request.method, action, host, request.POST)

        headers = {key[5:].replace('_', '-'): value
                   for key, value in request.META.items()
                   if key.startswith('HTTP_')}

        if action == 'RunInstances':
            r = run_instances(request)
            print('RESPONSE (%d):' % r.status_code, r.content, '\n\n\n')
            return r

        elif action == 'DescribeInstances':
            r = describe_instances(request)
            print('RESPONSE (%d):' % r.status_code, r.content, '\n\n\n')
            return r

        elif action == 'TerminateInstances':
            r = terminate_instances(request)
            print('RESPONSE (%d):' % r.status_code, r.content, '\n\n\n')
            return r

        # elif action == 'GetUser':
        #     host = "aws.amazon.com/iam"
        #     headers['HOST'] = "aws.amazon.com"

        path_info = request.path_info[4:]
        url = 'https://%s%s' % (host, path_info)
        print('url:', url)
        print('data:', request.body)
        print('headers:', headers)
        r = requests.post(url, data=request.body, headers=headers, allow_redirects=False)
        print('RESPONSE (%d):' % r.status_code, r.text, '\n\n\n')

        response = HttpResponse(r.text, r.status_code)

        hop_headers = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te',
                       'trailers', 'transfer-encoding', 'upgrade']

        for key, value in r.headers.items():
            if key.lower() not in hop_headers and key.lower() not in 'content-encoding':
                print('header:', key, value)
                response[key] = value

        return response