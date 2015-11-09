from django.shortcuts import redirect, render
from django.views.generic import View

import json
import re

from .models import ComputeGroup, Ec2ComputeInstance
from .lib.ec2 import Ec2Provider


class IndexView(View):
    def get(self, request):
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


class CreateComputeGroupView(View):
    providers = None

    def post(self, request):
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

class SyncView(View):
    providers = None

    def post(self, request):
        for provider in self.providers.values():
            provider.sync()

        return redirect('/')
