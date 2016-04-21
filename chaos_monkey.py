#!/usr/bin/env python3
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

import os
import random

access_key_id = os.environ['AWS_ACCESS_KEY_ID']
secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
regions = ['us-east-1', 'us-west-1', 'us-west-2']

driver_cls = get_driver(LibcloudProvider.EC2)

for region in regions:
    print('Region: %s' % region)
    driver = driver_cls(access_key_id, secret_access_key, region=region)
    nodes = driver.list_nodes()

    nodes_to_destroy = list(nodes)
    random.shuffle(nodes_to_destroy)

    if len(nodes_to_destroy):
        count = random.randrange(1, len(nodes_to_destroy))
        nodes_to_destroy = nodes_to_destroy[:count]

        for node in nodes_to_destroy:
            print('Destroying %s' % node.id)
            driver.destroy_node(node)
