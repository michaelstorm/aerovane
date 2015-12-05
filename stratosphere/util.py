import datetime
import json
import time

from functools import wraps

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

def retry(ExceptionToCheck, tries=4, delay=10, backoff=3, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param ExceptionToCheck: the exception to check. may be a tuple of
        exceptions to check
    :type ExceptionToCheck: Exception or tuple
    :param tries: number of times to try (not retry) before giving up
    :type tries: int
    :param delay: initial delay between retries in seconds
    :type delay: int
    :param backoff: backoff multiplier e.g. value of 2 will double the delay
        each retry
    :type backoff: int
    :param logger: logger to use. If None, print
    :type logger: logging.Logger instance
    """
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except ExceptionToCheck as e:
                    msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)

        return f_retry  # true decorator

    return deco_retry
