import datetime
import json

from libcloud.compute.drivers.ec2 import EC2NetworkInterface


class SimulatedFailureDriver(object):
    def list_nodes(*args, **kwargs):
        raise Exception()

    def list_sizes(*args, **kwargs):
        raise Exception()

    def list_images(*args, **kwargs):
        raise Exception()

    def create_node(*args, **kwargs):
        raise Exception()

    def destroy_node(*args, **kwargs):
        raise Exception()


class NodeJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, EC2NetworkInterface):
            return {'__ec2networkinterface__': True, 'value': o.__dict__}
        elif isinstance(o, datetime.datetime):
            return {'__datetime__': True, 'value': o.isoformat()}

        return json.JSONEncoder.default(self, o)


def decode_node_extra(dct):
    if dct is None:
        return None
    elif isinstance(dct, list) or isinstance(dct, set):
        return [decode_node_extra(i) for i in dct]
    elif isinstance(dct, dict):
        if '__ec2networkinterface__' in dct:
            return EC2NetworkInterface(**dct['value'])
        elif '__datetime__' in dct:
            return dateutil.parser.parse(dct['value'])
        else:
            new_dct = {}
            for key, value in dct.items():
                new_dct[key] = decode_node_extra(value)
            return new_dct
    else:
        return dct
