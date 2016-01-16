from annoying.fields import JSONField

from datetime import datetime, timedelta

from django.apps import apps
from django.db import models, transaction, OperationalError
from django.db.models import Q
from django.utils import timezone

from polymorphic import PolymorphicModel

from save_the_change.mixins import SaveTheChange

from ..models import ComputeInstance, ProviderConfiguration, ProviderSize
from ..util import HasLogger, retry, call_with_retry, BackoffError

import json

import traceback


class NoSizesAvailableError(Exception):
    pass


def update_distribution(func):
    def func_wrapper(self):
        def lock():
            print('ATTEMPTING LOCK')
            with transaction.atomic():
                cutoff_time = timezone.now() + timedelta(minutes=2)
                if self.updating_distribution and self.updating_distribution_time < cutoff_time:
                    raise BackoffError()
                else:
                    print('LOCKING')
                    self.updating_distribution = True
                    self.updating_distribution_time = timezone.now()
                    self.save()

        def unlock():
            print('ATTEMPTING UNLOCK')
            saved = False
            while not saved:
                try:
                    with transaction.atomic():
                        # load model at runtime to avoid import complexity
                        ComputeGroup = apps.get_model(app_label='stratosphere', model_name='ComputeGroup')
                        # don't re-save if deleted earlier
                        if ComputeGroup.objects.filter(pk=self.pk).exists():
                            print('UNLOCKING')
                            self.updating_distribution = False
                            self.save()

                        saved = True

                except OperationalError:
                    pass

        try:
            lock()
            func(self)
        finally:
            call_with_retry(unlock, OperationalError, tries=10)

    return func_wrapper


class ComputeGroupBase(PolymorphicModel, HasLogger, SaveTheChange):
    class Meta:
        abstract = True

    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    STOPPED = 'STOPPED'
    TERMINATED = 'TERMINATED'

    STATE_CHOICES = (
        (PENDING, 'Pending'),
        (RUNNING, 'Running'),
        (STOPPED, 'Stopped'),
        (TERMINATED, 'Terminated'),
    )

    user_configuration = models.ForeignKey('UserConfiguration', related_name='compute_groups')
    instance_count = models.IntegerField()
    cpu = models.IntegerField()
    memory = models.IntegerField()
    name = models.CharField(max_length=128)
    provider_policy = JSONField()
    size_distribution = JSONField()
    updating_distribution = models.BooleanField(default=False)
    updating_distribution_time = models.DateTimeField(blank=True, null=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=PENDING)
    authentication_method = models.ForeignKey('AuthenticationMethod', related_name='compute_groups')

    def provider_states(self):
        provider_states_map = {}

        for provider_name in self.provider_policy:
            provider_configuration = ProviderConfiguration.objects.get(provider_name=provider_name)
            provider_instances = self.instances.filter(provider_image__provider__name=provider_name)
            running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, provider_instances)))
            pending_count = len(list(filter(lambda i: i.state in (None, ComputeInstance.PENDING, ComputeInstance.REBOOTING), provider_instances)))
            terminated_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.RUNNING, ComputeInstance.PENDING, ComputeInstance.REBOOTING) and not i.terminated,
                                               provider_instances)))

            provider_states_map[provider_name] = {
                'running': running_count,
                'pending': pending_count,
                'terminated': terminated_count,
                'pretty_name': provider_configuration.provider.pretty_name,
                'icon_path': provider_configuration.provider.icon_path,
            }

        return provider_states_map

    @update_distribution
    def check_instance_distribution(self):
        self.logger.warning('Got lock')

        self.logger.warning('%s state: %s' % (self.name, self.state))

        instances_flat = list(self.instances.all())
        running_count = len(list(filter(lambda i: i.state == ComputeInstance.RUNNING, instances_flat)))
        non_pending_count = len(list(filter(lambda i: i.state not in (None, ComputeInstance.PENDING), instances_flat)))
        non_terminated_count = len(list(filter(lambda i: i.state not in (ComputeInstance.TERMINATED, ComputeInstance.UNKNOWN), instances_flat)))
        non_running_instances = list(filter(lambda i: i.state != ComputeInstance.RUNNING, instances_flat))

        if self.state == self.TERMINATED:
            self.logger.info('Compute group state is TERMINATED. Remaining non-terminated instances: %d' % non_terminated_count)
            if non_terminated_count == 0:
                self.logger.info('Deleting self.')
                self.delete()
        else:
            if self.state == self.PENDING and non_pending_count >= self.instance_count:
                self.state = self.RUNNING

            self.logger.warn('running_count < self.instance_count = %d < %d = %s' %
                             (running_count, self.instance_count, running_count < self.instance_count))

            if running_count < self.instance_count:
                bad_provider_ids = set([instance.provider_configuration.pk for instance in self.instances.filter(~Q(state__in=[None, ComputeInstance.PENDING, ComputeInstance.RUNNING]))])
                good_provider_ids = [provider.pk for provider in
                                     self.user_configuration.provider_configurations.exclude(pk__in=bad_provider_ids)]

                self.logger.warning('bad_provider_ids: %s' % bad_provider_ids)
                self.logger.warning('good_provider_ids: %s' % good_provider_ids)

            if running_count != self.instance_count:
                self.rebalance_instances()

    def rebalance_instances(self, provider_ids=None):
        best_sizes = self._get_best_sizes(provider_ids)

        if len(best_sizes) == 0:
            raise NoSizesAvailableError()

        instance_counts_by_size_id = self._get_size_distribution(best_sizes)
        self.size_distribution = instance_counts_by_size_id
        self.save()

        self._create_compute_instances()

    @retry(OperationalError)
    def terminate(self):
        self.state = self.TERMINATED
        self.instance_count = 0
        self.save()