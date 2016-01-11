import datetime
import json
import logging
import time

from django.contrib.staticfiles.storage import CachedFilesMixin
from functools import wraps
from libcloud.compute.drivers.ec2 import EC2NetworkInterface
from storages.backends.s3boto import S3BotoStorage


class HasLogger(object):
    _logger = None

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)

        return self._logger


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


def call_with_retry(f, exception_type, tries=4, delay=10, backoff=3, logger=None, args=[], kwargs={}):
    mtries, mdelay = tries, delay
    while mtries > 1:
        try:
            return f(*args, **kwargs)
        except exception_type as e:
            msg = "%s, Retrying in %d seconds..." % (str(e), mdelay)
            if logger:
                logger.warning(msg)
            else:
                print(msg)
            time.sleep(mdelay)
            mtries -= 1
            mdelay *= backoff
    return f(*args, **kwargs)


def retry(exception_type, tries=4, delay=1, backoff=3, logger=None):
    """Retry calling the decorated function using an exponential backoff.

    http://www.saltycrane.com/blog/2009/11/trying-out-retry-decorator-python/
    original from: http://wiki.python.org/moin/PythonDecoratorLibrary#Retry

    :param exception_type: the exception to check. may be a tuple of
        exceptions to check
    :type exception_type: Exception or tuple
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
            return call_with_retry(f, exception_type, tries=tries, delay=delay, backoff=backoff,
                                   logger=logger, args=args, kwargs=kwargs)

        return f_retry  # true decorator

    return deco_retry


class S3HashedFilesStorage(CachedFilesMixin, S3BotoStorage):
    """
    Extends S3BotoStorage to also save hashed copies (i.e.
    with filenames containing the file's MD5 hash) of the
    files it saves.
    """
    pass
