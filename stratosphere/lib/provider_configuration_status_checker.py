from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from libcloud.compute.types import NodeState

from stratosphere.models import ComputeInstance
from stratosphere.util import thread_local

import traceback


class ProviderConfigurationStatusChecker(object):
    def set_enabled(self, enabled_value):
        with transaction.atomic():
            if enabled_value:
                failed_instances = self.instances.filter(ComputeInstance.unignored_failed_instances_query())
                for instance in failed_instances:
                    instance.failure_ignored = True
                    instance.save()

                self.enabled = True
                self.save()

            else:
                self.enabled = False
                self.save()

    def max_failure_count(self):
        instance_count = self.instances.count()
        return instance_count if instance_count < 3 else 3

    def failure_count(self, now):
        one_hour_ago = now - timedelta(hours=1)
        return self.instances.filter(ComputeInstance.unignored_failed_instances_query() & Q(failed_at__gte=one_hour_ago)).count()

    @thread_local(DB_OVERRIDE='serializable')
    def check_enabled(self):
        now = timezone.now()
        max_failure_count_value = self.max_failure_count()
        failure_count_value = self.failure_count(now)

        self.logger.info('Instance count: %d, max failure count: %d, failure count: %d' %
                         (instance_count, max_failure_count_value, failure_count_value))

        if self.enabled:
            if max_failure_count_value > 0 and failure_count_value >= max_failure_count_value:
                self.logger.warn('Disabling provider %d (%s)' % (self.pk, self.provider.name))
                self.enabled = False
                self.save()
        else:
            self.logger.info('Provider %d (%s) already disabled' % (self.pk, self.provider.name))

    @thread_local(DB_OVERRIDE='serializable')
    def check_failed_instances(self):
        bad_instances = []

        now = timezone.now()
        five_minutes_ago = now - timedelta(minutes=5)
        bad_pending_instances_query = ComputeInstance.pending_instances_query() & Q(created_at__lt=five_minutes_ago)
        bad_pending_instances = self.instances.filter(bad_pending_instances_query)
        bad_instances.extend(list(bad_pending_instances))

        if len(bad_pending_instances) > 0:
            self.logger.warn('Found %d expired pending instances for provider %s: %s' %
                             (len(bad_pending_instances), self.pk, bad_pending_instances))

        bad_state_instances_query =  ~ComputeInstance.running_instances_query()
        bad_state_instances_query &= ~ComputeInstance.pending_instances_query()
        bad_state_instances_query &= ~ComputeInstance.unavailable_instances_query()
        bad_state_instances = self.instances.filter(bad_state_instances_query)
        bad_instances.extend(list(bad_state_instances))

        if len(bad_state_instances) > 0:
            self.logger.warn('Found %d instances in an unexpected state for provider %s: %s' %
                             (len(bad_state_instances), self.pk, bad_state_instances))

        # TODO this is where all the other health checks would go

        for instance in bad_instances:
            self.logger.warn('Marking instance %s failed for provider %s' % (instance.pk, self.pk))
            self.logger.warn('state: %s, failed: %s, destroyed: %s' % (instance.state, instance.failed, instance.destroyed))
            instance.failed = True
            instance.failed_at = now
            instance.save()

    def update_instance_statuses(self):
        try:
            libcloud_nodes = self.driver.list_nodes()

        except Exception as e:
            print('Error listing nodes of %s' % self)

            traceback.print_exc()
            for instance in self.instances.all():
                instance.state = ComputeInstance.UNKNOWN
                instance.save()

        else:
            now = timezone.now()
            thirty_seconds_ago = now - timedelta(seconds=30)

            # exclude ComputeInstances whose libcloud node creation jobs have not yet run
            for instance in self.instances.filter(~Q(external_id=None)):
                nodes = list(filter(lambda node: node.id == instance.external_id, libcloud_nodes))

                if len(nodes) == 0:
                    # There's a race condition between assigning an instance an external_id when it's created and the
                    # list_nodes() query returning, so wait 30 seconds before a missing instance is considered
                    # terminated (and thus failed).
                    if instance.created_at >= thirty_seconds_ago:
                        instance.state = ComputeInstance.TERMINATED
                else:
                    node = nodes[0]

                    self.logger.warn('Remote node %s state: %s' % (instance.pk, NodeState.tostring(node.state)))

                    instance.state = NodeState.tostring(node.state)
                    instance.private_ips = node.private_ips
                    instance.public_ips = node.public_ips

                # prevent too many history instances from being created
                if instance.has_changed:
                    if 'state' in instance.changed_fields:
                        self.logger.info('Updating state of instance %s from %s to %s' % (instance.pk, instance.old_values['state'], instance.state))

                    instance.save()

            self.check_failed_instances()

            with thread_local(DB_OVERRIDE='serializable'):
                self.user_configuration.take_instance_states_snapshot_if_changed()