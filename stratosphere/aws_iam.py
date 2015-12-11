from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt

import boto.ec2
from boto.iam.connection import IAMConnection

from xml.sax.saxutils import escape as xml_escape

import requests


def format_key(key):
    parts = key.split('_')
    return ''.join([p[0].upper() + p[1:] for p in parts])


def to_xml(node, namespace="https://iam.amazonaws.com/doc/2010-05-08/"):
    if isinstance(node, dict):
        ret = ''
        for key, value in node.items():
            formatted_key = format_key(key)
            open_tag = '<%s%s>' % (formatted_key, ' xmlns="%s"' % namespace if namespace is not None else '')
            ret += open_tag + to_xml(value, namespace=None) + '</' + formatted_key + '>'
        return ret
    else:
        return xml_escape(node)

@csrf_exempt
def initial(request):
    action = request.POST['Action']

    print('XXX', request.method, action, request.POST)
    print('META', request.META.keys())

    region = request.get_host().split('.')[1]

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

    # print('ARGS:', args)

    hop_headers = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade']

    headers = {key[5:].replace('_', '-'): value for key, value in request.META.items() if key.startswith('HTTP_')}
    r = requests.post('https://ec2.us-east-1.amazonaws.com/', data=request.body, headers=headers)
    print('RESPONSE:', r.text)

    # ec2 = boto.ec2.connect_to_region(region_name=region)

    # response = ec2.run_instances(**args)
    # print(to_xml(response))
    response = HttpResponse(r.text, r.status_code)

    for key, value in r.headers.items():
        if key.lower() not in hop_headers and key.lower() not in 'content-encoding':
            print('header:', key, value)
            response[key] = value

    return response