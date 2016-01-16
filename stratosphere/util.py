import datetime
import json
import logging
import time
import traceback

from django.contrib.staticfiles.storage import CachedFilesMixin
from django.utils import timezone
from functools import wraps
from libcloud.compute.drivers.ec2 import EC2NetworkInterface
from storages.backends.s3boto import S3BotoStorage


# from http://stackoverflow.com/a/11111177
epoch = datetime.datetime.utcfromtimestamp(0)


def unix_time_millis(dt):
    return (timezone.make_naive(dt) - epoch).total_seconds() * 1000


class BackoffError(Exception):
    pass


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
    ret = None
    succeeded = False
    failed_try = False

    while mtries > 1 and not succeeded:
        try:
            ret = f(*args, **kwargs)
            succeeded = True
        except exception_type as e:
            task_traceback = ''.join(traceback.format_list(traceback.extract_stack()))
            exception_traceback = ''.join(traceback.format_list(traceback.extract_tb(e.__traceback__)))

            msg = "%s failed (%s: %s), retrying in %d seconds. Task traceback:\n%s\nException traceback:\n%s" % \
                  (f.__name__, e.__class__.__qualname__, str(e), mdelay, task_traceback, exception_traceback)

            if logger:
                logger.warning(msg)
            else:
                print(msg)

            time.sleep(mdelay)
            failed_try = True
            mtries -= 1
            mdelay *= backoff

    if succeeded:
        if failed_try:
            msg = "%s succeeded" % f.__name__
            if logger:
                logger.warning(msg)
            else:
                print(msg)
    else:
        ret = f(*args, **kwargs)

        if failed_try:
            msg = "%s succeeded" % f.__name__
            if logger:
                logger.warning(msg)
            else:
                print(msg)

    return ret


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
