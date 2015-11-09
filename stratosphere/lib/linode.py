import os
import requests

#from ..models import LinodeComputeInstance


class LinodeProvider(object):
    default_datacenter_id = '3'

    def _get_instances(self):
        return []

    def _terminate_instances(self, instance_ids):
        pass

    def create_instances(self, num_instances, instance_type):
        create_config_params = {
            'api_key': os.environ['LINODE_API_KEY'],
            'api_action': 'linode.create',
            'datacenterid': self.default_datacenter_id,
            'planid': instance_type,
        }
        return [str(requests.get('https://api.linode.com', params=create_config_params).json()['DATA']['LinodeID'])
                for i in range(num_instances)]

    def sync(self):
        pass
