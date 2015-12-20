from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

import json
import random
import re
import requests
import string

from .aws_api import *
from .models import Ec2ProviderConfiguration


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
    provider_configuration = Ec2ProviderConfiguration.objects.get(access_key_id=access_key_id)

    name_suffix = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
    name = 'terraform-%s' % name_suffix

    size = provider_configuration.provider_sizes.get(external_id=args['instance_type'])

    provider_image = provider_configuration.provider_images.get(image_id=args['image_id'])
    operating_system_image = provider_image.disk_image.operating_system_images.first()

    provider_policy = {provider_name: 'auto' for provider_name
                                      in user_configuration.provider_configurations.all()}
    provider_policy_str = json.dumps(provider_policy)

    compute_group_attributes = {
        'user_configuration': provider_configuration.user_configuration,
        'name': name,
        'cpu': size.vcpus,
        'memory': size.ram,
        'instance_count': args['MaxCount'],
        'image': operating_system_image,
        'provider_policy': provider_policy_str,
        'authentication_method': authentication_method,
    }

    group = OperatingSystemComputeGroup.objects.create(**compute_group_attributes)

    return run_instances_response(args['instance_type'], args['image_id'])


@csrf_exempt
def initial(request):
    host = request.get_host()
    action = request.POST['Action']

    print('XXX', request.method, action, host, request.POST)

    if action == 'RunInstances':
        return run_instances(request)

    headers = {key[5:].replace('_', '-'): value
               for key, value in request.META.items()
               if key.startswith('HTTP_')}

    path_info = request.path_info[4:]
    url = 'https://%s%s/' % (host, path_info)
    print('url:', url)
    print('data:', request.body)
    print('headers:', headers)
    r = requests.post(url, data=request.body, headers=headers)
    print('RESPONSE:', r.text, '\n\n\n')

    response = HttpResponse(r.text, r.status_code)

    hop_headers = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te',
                   'trailers', 'transfer-encoding', 'upgrade']

    for key, value in r.headers.items():
        if key.lower() not in hop_headers and key.lower() not in 'content-encoding':
            print('header:', key, value)
            response[key] = value

    return response