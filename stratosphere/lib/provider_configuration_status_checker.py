from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from libcloud.compute.types import NodeState

from stratosphere.models import ComputeInstance
from stratosphere.util import thread_local

import traceback


class ProviderConfigurationStatusChecker(object):
    def set_enabled(self, enabled):
        with transaction.atomic():
            if enabled:
                failed_instances = self.instances.filter(ComputeInstance.unignored_failed_instances_query())
                for instance in failed_instances:
                    instance.failure_ignored = True
                    instance.save()

                self.enabled = True
                self.save()

            else:
                self.enabled = False
                self.save()

    @thread_local(DB_OVERRIDE='serializable')
    def check_enabled(self):
        instance_count = self.instances.count()
        max_failure_count = instance_count if instance_count < 3 else 3
        failure_count = self.instances.filter(ComputeInstance.unignored_failed_instances_query()).count()

        self.logger.info('Instance count: %d, max failure count: %d, failure count: %d' %
                         (instance_count, max_failure_count, failure_count))

        if self.enabled:
            if max_failure_count > 0 and failure_count >= max_failure_count:
                self.logger.warn('Disabling provider %d (%s)' % (self.pk, self.provider.name))
                self.enabled = False
                self.save()
        else:
            self.logger.info('Provider %d (%s) already disabled' % (self.pk, self.provider.name))

    def check_failed_instances(self):
        now = timezone.now()
        query = ComputeInstance.terminated_instances_query(now) & Q(failed=False)
        terminated_not_failed_instances = self.instances.filter(query)

        self.logger.info('Found %d terminated instances that are not yet failed for provider %d' %
                         (terminated_not_failed_instances.count(), self.provider.pk))

        for instance in terminated_not_failed_instances:
            self.logger.warn('Marking instance %d failed' % instance.pk)
            instance.failed = True
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
            # exclude ComputeInstances whose libcloud node creation jobs have not yet run
            for instance in self.instances.filter(~Q(external_id=None)):
                nodes = list(filter(lambda node: node.id == instance.external_id, libcloud_nodes))

                previous_state = instance.state

                if len(nodes) == 0:
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

            with thread_local(DB_OVERRIDE='serializable'):
                self.user_configuration.take_instance_states_snapshot_if_changed()