import uuid

def run_instances_response(instance_id, image_id):
	request_id = uuid.uuid4()

	return """
<?xml version="1.0" encoding="UTF-8"?>
<RunInstancesResponse xmlns="http://ec2.amazonaws.com/doc/2015-10-01/">
    <requestId>{request_id}</requestId>
    <reservationId>r-62534ecb</reservationId>
    <ownerId>671861320306</ownerId>
    <groupSet>
        <item>
            <groupId>sg-ba93e5d3</groupId>
            <groupName>default</groupName>
        </item>
    </groupSet>
    <instancesSet>
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
    </instancesSet>
</RunInstancesResponse>
""".format({'request_id': request_id, 'instance_id': instance_id, 'image_id': image_id})