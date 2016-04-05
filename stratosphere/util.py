import datetime
import json
import logging
import random
import threading
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


class HasLogger(object):
    _logger = None

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(self.__class__.__name__)

        return self._logger


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


def schedule_random_delay(task, base_delay, half_interval, *args):
    delay = base_delay + random.uniform(half_interval * -1, half_interval)
    task.apply_async(args=args, countdown=delay)


def schedule_random_default_delay(task, *args):
    schedule_random_delay(task, 5, 2, *args)


# from https://dzone.com/articles/django-switching-databases
_stratosphere_threadlocal = threading.local()


class thread_local(object):
    """ a decorator that wraps a function in a thread local definition block
    useful for passing variables down the stack w/o actually passing them
    examples: what database to read from, whether to cache queries, etc
    adapted from django.test.utils.override_settings

    Usage:

    @thread_local(SITE_NAME_SHORT='foobar')
    def override(request):
        ...

    """

    def __init__(self, **kwargs):
        self.options = kwargs

    def __enter__(self):
        for attr, value in self.options.items():
            if not hasattr(_stratosphere_threadlocal, attr):
                setattr(_stratosphere_threadlocal, attr, [])

            getattr(_stratosphere_threadlocal, attr).append(value)

    def __exit__(self, exc_type, exc_value, traceback):
        for attr in self.options.keys():
            getattr(_stratosphere_threadlocal, attr).pop()

    def __call__(self, test_func):

        @wraps(test_func)
        def inner(*args, **kwargs):
            # the thread_local class is also a context manager
            # which means it will call __enter__ and __exit__
            with self:
                return test_func(*args, **kwargs)

        return inner


def get_thread_local(attr, default=None):
    """ use this method from lower in the stack to get the value """
    stack = getattr(_stratosphere_threadlocal, attr, [])
    return stack[-1] if len(stack) > 0 else default


# no-argument decorators work differently than with-argument decorators, so we
# have to do some bridging between them
class static_thread_local(thread_local):
    def __init__(self, func, **kwargs):
        self.func = func
        super().__init__(**kwargs)

    def __call__(self, *args, **kwargs):
        return super().__call__(self.func)(*args, **kwargs)