from .models import *

import uuid

def _run_instances_response_item(image_id, instance_type, instance_id):
    return """
<item>
    <instanceId>{instance_id}</instanceId>
    <imageId>{image_id}</imageId>
    <instanceState>
        <code>0</code>
        <name>pending</name>
    </instanceState>
    <privateDnsName/>
    <dnsName/>
    <reason/>
    <amiLaunchIndex>0</amiLaunchIndex>
    <productCodes/>
    <instanceType>{instance_type}</instanceType>
    <launchTime>2015-12-19T23:55:07.000Z</launchTime>
    <placement>
        <availabilityZone>us-east-1a</availabilityZone>
        <groupName/>
        <tenancy>default</tenancy>
    </placement>
    <kernelId>aki-919dcaf8</kernelId>
    <monitoring>
        <state>disabled</state>
    </monitoring>
    <groupSet>
        <item>
            <groupId>sg-ba93e5d3</groupId>
            <groupName>default</groupName>
        </item>
    </groupSet>
    <stateReason>
        <code>pending</code>
        <message>pending</message>
    </stateReason>
    <architecture>x86_64</architecture>
    <rootDeviceType>ebs</rootDeviceType>
    <rootDeviceName>/dev/sda1</rootDeviceName>
    <blockDeviceMapping/>
    <virtualizationType>paravirtual</virtualizationType>
    <clientToken/>
    <hypervisor>xen</hypervisor>
    <networkInterfaceSet/>
    <ebsOptimized>false</ebsOptimized>
</item>
""".format(instance_id=instance_id, instance_type=instance_type, image_id=image_id)


def run_instances_response(group_id, image_id, instance_type, instance_ids):
    request_id = uuid.uuid4()

    instances = "\n".join([_run_instances_response_item(image_id, instance_type, instance_id) for instance_id in instance_ids])

    return """
<?xml version="1.0" encoding="UTF-8"?>
<RunInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2015-10-01/">
    <requestId>{request_id}</requestId>
    <reservationId>{group_id}</reservationId>
    <ownerId>671861320306</ownerId>
    <groupSet>
        <item>
            <groupId>sg-ba93e5d3</groupId>
            <groupName>default</groupName>
        </item>
    </groupSet>
    <instancesSet>
        {instances}
    </instancesSet>
</RunInstancesResponse>
""".format(request_id=request_id, group_id=group_id, instance_type=instance_type, instances=instances)


def describe_instances_response(group_id, image_id, instance_type, instance_id, state):
    request_id = uuid.uuid4()

    state_name = 'pending' if state is None else state.lower()

    if state is None or state == ComputeGroup.PENDING:
        state_code = 0
    elif state == ComputeGroup.RUNNING:
        state_code = 16
    elif state == ComputeGroup.STOPPED:
        state_code = 80
    elif state == ComputeGroup.TERMINATED:
        state_code = 48

    return """
<?xml version="1.0" encoding="UTF-8"?>
<DescribeInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2015-10-01/">
    <requestId>{request_id}</requestId>
    <reservationSet>
        <item>
            <reservationId>{group_id}</reservationId>
            <ownerId>671861320306</ownerId>
            <groupSet/>
            <instancesSet>
                <item>
                    <instanceId>{instance_id}</instanceId>
                    <imageId>{image_id}</imageId>
                    <instanceState>
                        <code>{state_code}</code>
                        <name>{state_name}</name>
                    </instanceState>
                    <privateDnsName>ip-172-31-10-140.us-west-2.compute.internal</privateDnsName>
                    <dnsName>ec2-52-35-73-110.us-west-2.compute.amazonaws.com</dnsName>
                    <reason/>
                    <amiLaunchIndex>0</amiLaunchIndex>
                    <productCodes/>
                    <instanceType>{instance_type}</instanceType>
                    <launchTime>2015-12-21T23:08:30.000Z</launchTime>
                    <placement>
                        <availabilityZone>us-west-2c</availabilityZone>
                        <groupName/>
                        <tenancy>default</tenancy>
                    </placement>
                    <monitoring>
                        <state>disabled</state>
                    </monitoring>
                    <subnetId>subnet-0585d243</subnetId>
                    <vpcId>vpc-be9481dc</vpcId>
                    <privateIpAddress>172.31.10.140</privateIpAddress>
                    <ipAddress>52.35.73.110</ipAddress>
                    <sourceDestCheck>true</sourceDestCheck>
                    <groupSet>
                        <item>
                            <groupId>sg-ba93e5d3</groupId>
                            <groupName>default</groupName>
                        </item>
                    </groupSet>
                    <architecture>x86_64</architecture>
                    <rootDeviceType>instance-store</rootDeviceType>
                    <blockDeviceMapping/>
                    <virtualizationType>hvm</virtualizationType>
                    <clientToken/>
                    <hypervisor>xen</hypervisor>
                    <networkInterfaceSet>
                        <item>
                            <networkInterfaceId>eni-ae893df4</networkInterfaceId>
                            <subnetId>subnet-0585d243</subnetId>
                            <vpcId>vpc-be9481dc</vpcId>
                            <description/>
                            <ownerId>671861320306</ownerId>
                            <status>in-use</status>
                            <macAddress>0a:b5:10:11:76:17</macAddress>
                            <privateIpAddress>172.31.10.140</privateIpAddress>
                            <privateDnsName>ip-172-31-10-140.us-west-2.compute.internal</privateDnsName>
                            <sourceDestCheck>true</sourceDestCheck>
                            <groupSet>
                                <item>
                                    <groupId>sg-ba93e5d3</groupId>
                                    <groupName>default</groupName>
                                </item>
                            </groupSet>
                            <attachment>
                                <attachmentId>eni-attach-8666d489</attachmentId>
                                <deviceIndex>0</deviceIndex>
                                <status>attaching</status>
                                <attachTime>2015-12-21T23:08:30.000Z</attachTime>
                                <deleteOnTermination>true</deleteOnTermination>
                            </attachment>
                            <association>
                                <publicIp>52.35.73.110</publicIp>
                                <publicDnsName>ec2-52-35-73-110.us-west-2.compute.amazonaws.com</publicDnsName>
                                <ipOwnerId>amazon</ipOwnerId>
                            </association>
                            <privateIpAddressesSet>
                                <item>
                                    <privateIpAddress>172.31.10.140</privateIpAddress>
                                    <privateDnsName>ip-172-31-10-140.us-west-2.compute.internal</privateDnsName>
                                    <primary>true</primary>
                                    <association>
                                    <publicIp>52.35.73.110</publicIp>
                                    <publicDnsName>ec2-52-35-73-110.us-west-2.compute.amazonaws.com</publicDnsName>
                                    <ipOwnerId>amazon</ipOwnerId>
                                    </association>
                                </item>
                            </privateIpAddressesSet>
                        </item>
                    </networkInterfaceSet>
                    <ebsOptimized>false</ebsOptimized>
                </item>
            </instancesSet>
        </item>
    </reservationSet>
</DescribeInstancesResponse>
""".format(request_id=request_id, group_id=group_id, image_id=image_id, instance_type=instance_type,
           instance_id=instance_id, state_name=state_name, state_code=state_code)


def terminate_instances_response(instance_id):
    request_id = uuid.uuid4()

    return """
<TerminateInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2015-10-01/">
    <requestId>{request_id}</requestId>
    <instancesSet>
        <item>
            <instanceId>{instance_id}</instanceId>
            <currentState>
                <code>32</code>
                <name>shutting-down</name>
            </currentState>
            <previousState>
                <code>16</code>
                <name>running</name>
            </previousState>
        </item>
    </instancesSet>
</TerminateInstancesResponse> 
""".format(request_id=request_id, instance_id=instance_id)