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

    provider_image = ProviderImage.objects.get(image_id=args['image_id'], provider__name__startswith='aws')
    operating_system_image = provider_image.disk_image.disk_image_mappings.first().operating_system_image

    user_configuration = provider_configuration.user_configuration
    provider_policy = {pc.provider_name: 'auto' for pc
                                      in user_configuration.provider_configurations.all()}

    attributes = {
        'user_configuration': provider_configuration.user_configuration,
        'name': name,
        'cpu': int(provider_size.vcpus),
        'memory': int(provider_size.ram),
        'instance_count': int(args['max_count']),
        'image': operating_system_image,
        'provider_policy': provider_policy,
        'size_distribution': {},
        'authentication_method': user_configuration.authentication_methods.instance_of(KeyAuthenticationMethod).first(),
    }

    compute_group = ComputeGroup.objects.filter(cpu=attributes['cpu'], memory=attributes['memory'],
                                                image=attributes['image']).first()

    compute_group = ComputeGroup.objects.create(**attributes)
    compute_group.rebalance_instances()

    response_xml = run_instances_response(compute_group.pk, args['image_id'], args['instance_type'])
    return HttpResponse(response_xml, 201)


def describe_instances(request):
    instance_id = request.POST['InstanceId.1']
    compute_group = ComputeGroup.objects.get(pk=instance_id)

    response_xml = describe_instances_response(compute_group.pk, compute_group.state)
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