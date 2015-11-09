import boto.ec2

from ..models import Ec2ComputeInstance


class Ec2Provider(object):
    regions = ['us-west-1'] #['us-east-1','us-west-1','us-west-2','eu-west-1','sa-east-1',
               #     'ap-southeast-1','ap-southeast-2','ap-northeast-1']
    default_region = 'us-west-1'
    default_ami = 'ami-d5ea86b5'

    def _get_instances(self):
        instances = []
        for region in self.regions:
            ec2_conn = boto.ec2.connect_to_region(region)
            instances.extend(ec2_conn.get_only_instances())
        return instances

    def _terminate_instances(self, instance_ids):
        ec2_conn = boto.ec2.connect_to_region(self.default_region)

        if len(instance_ids) > 0:
            ec2_conn.terminate_instances(instance_ids=instance_ids)

    def create_instances(self, num_instances, instance_type):
        ec2_conn = boto.ec2.connect_to_region(self.default_region)

        if num_instances > 0:
            reservation = ec2_conn.run_instances(self.default_ami, min_count=num_instances,
                                                 max_count=num_instances, instance_type=instance_type)
            return [instance.id for instance in reservation.instances]
        else:
            return []

    def sync(self):
        ec2_instances = self._get_instances()
        orphan_local_instances = Ec2ComputeInstance.objects.exclude(external_id__in=[instance.id for instance in ec2_instances])
        orphan_local_instances.delete()

        live_remote_instances = filter(lambda instance: instance.state not in ['shutting-down', 'terminated'], ec2_instances)
        orphan_remote_instances = [ec2_instance.id for ec2_instance in live_remote_instances
                                   if len(Ec2ComputeInstance.objects.filter(external_id=ec2_instance.id)) > 0]
        self._terminate_instances(orphan_remote_instances)
