from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import View

import base64
import json
import re

from .models import ComputeGroup, Ec2ComputeInstance
from .lib.ec2 import Ec2Provider


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
    compute_groups = ComputeGroup.objects.all()
    groups = []

    for compute_group in compute_groups:
        group = {}
        group['group'] = compute_group

        providers = compute_group.provider_states()
        group['providers'] = providers

        groups.append(group)

    context = {
        'compute_groups': groups,
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
        group = ComputeGroup.objects.create(cpu=cpu, memory=memory, instance_count=instance_count, name=name, provider_policy=provider_policy_str)

        return redirect('/')


@basicauth
def sync(request):
    for provider in self.providers.values():
        provider.sync()

    return redirect('/')
