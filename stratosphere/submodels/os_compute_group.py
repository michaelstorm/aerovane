from datetime import timedelta

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

# from simple_history.models import HistoricalRecords

from ..models import ComputeGroup, ComputeInstance, ProviderSize


class ImageComputeGroupBase(ComputeGroup):
    class Meta:
        abstract = True

    image = models.ForeignKey('DiskImage', related_name='compute_groups')


class OperatingSystemComputeGroupBase(ComputeGroup):
    class Meta:
        abstract = True

    image = models.ForeignKey('OperatingSystemImage', related_name='compute_groups')

    def _get_best_sizes(self, allowed_provider_ids=None):
        best_sizes = {}
        for provider_name in self.provider_policy:
            provider_configuration = self.user_configuration.provider_configurations.get(provider_name=provider_name)

            if allowed_provider_ids is None or provider_configuration.pk in allowed_provider_ids:
                available_sizes = []

                provider_image = provider_configuration.available_provider_images.filter(disk_image__disk_image_mappings__operating_system_image=self.image).first()
                if provider_image is not None:
                    provider_sizes = provider_configuration.get_available_sizes(provider_image=provider_image, cpu=self.cpu, memory=self.memory)
                    available_sizes.extend(provider_sizes)

                available_sizes.sort(key=lambda s: s.price)
                if len(available_sizes) > 0:
                    best_sizes[provider_name] = available_sizes[0]

        return best_sizes

    def _get_size_distribution(self, sizes):
        # sort to ensure consistency across multiple runs, e.g. when a size has the
        # same price in multiple AWS regions
        sizes_list = sorted(sizes.values(), key=lambda s: s.pk) # sort on secondary key
        self.logger.warning('sizes_list: %s' % sizes_list)

        instance_counts = {}

        # if len(sizes) == 0, we get into an infinite loop
        if len(sizes) > 0:
            while sum(instance_counts.values()) < self.instance_count:
                remaining_instance_count = self.instance_count - sum(instance_counts.values())
                provider_instance_count = int(remaining_instance_count/len(sizes))

                print('provider_instance_count = int(remaining_instance_count)/len(sizes)) = int(%d/%d) = int(%s) = %d' %
                      (remaining_instance_count, len(sizes), remaining_instance_count/len(sizes),
                       int(remaining_instance_count/len(sizes))))

                for provider_size in sizes_list:
                    print('sum(instance_counts.values()) < self.instance_count = %d < %d = %s' % (sum(instance_counts.values()), self.instance_count, sum(instance_counts.values()) < self.instance_count))

                    print('provider_instance_count: %d' % provider_instance_count)
                    if provider_instance_count == 0 and sum(instance_counts.values()) < self.instance_count:
                        adjusted_provider_instance_count = 1
                    else:
                        adjusted_provider_instance_count = provider_instance_count

                    print('adjusted_provider_instance_count for %d: %d' % (provider_size.pk, adjusted_provider_instance_count))

                    # the database converts to string keys anyway, so we do it here for consistency
                    key = str(provider_size.pk)
                    if key in instance_counts:
                        instance_counts[key] += adjusted_provider_instance_count
                    else:
                        instance_counts[key] = adjusted_provider_instance_count

                    print('instance_counts: %s' % instance_counts)

        return instance_counts

    def pending_or_running_count(self, provider_size):
        now = timezone.now()
        return self.instances.filter(
            Q(provider_size=provider_size)
            & (Q(state=ComputeInstance.RUNNING)
               | Q(state=None,
                   last_request_start_time__gt=now - timedelta(minutes=2))
               | Q(state=ComputeInstance.PENDING,
                   last_request_start_time__gt=now - timedelta(minutes=5))
        )).count()

    def _create_compute_instances(self):
        with transaction.atomic():
            self.logger.warning('size_distribution: %s' % self.size_distribution)
            terminate_instances = []

            for provider_size_id, instance_count in self.size_distribution.items():
                provider_size = ProviderSize.objects.get(pk=provider_size_id)
                provider_configuration = provider_size.provider_configuration

                pending_or_running_count = self.pending_or_running_count(provider_size)

                running_provider_instances = self.instances.filter(provider_size=provider_size, state=ComputeInstance.RUNNING)
                running_count = running_provider_instances.count()

                now = timezone.now()
                two_minutes_ago = now - timedelta(minutes=2)
                created_count = self.instances.filter(provider_size=provider_size, state=None,
                                                      last_request_start_time__gt=two_minutes_ago).count()

                five_minutes_ago = now - timedelta(minutes=5)
                pending_count = self.instances.filter(provider_size=provider_size, state=ComputeInstance.PENDING,
                                                      last_request_start_time__gt=five_minutes_ago).count()

                self.logger.warning('%s (%d) counts: %d created, %d pending, %d running, %d pending or running' %
                                    (provider_size, provider_size.pk, created_count, pending_count, running_count,
                                     pending_or_running_count))

                if pending_or_running_count < instance_count:
                    for i in range(instance_count - pending_or_running_count):
                        self.logger.warning('creating instance for size %s' % provider_size)
                        instance_name = '%s-%d' % (self.name, i)
                        ComputeInstance.create_with_provider(provider_configuration=provider_configuration, provider_size=provider_size,
                                                             authentication_method=self.authentication_method, compute_group=self)
                elif running_count > instance_count:
                    terminate_instances.extend(list(running_provider_instances)[:running_count - instance_count])

            # TODO make sure this squares with multi-row transaction isolation
            missing_size_instances = self.instances.filter(~Q(provider_size__pk__in=self.size_distribution.keys()))
            terminate_instances.extend(missing_size_instances)

            for instance in terminate_instances:
                self.logger.warning('terminating instance %s for size %s' % (instance, instance.provider_size))
                instance.terminate()