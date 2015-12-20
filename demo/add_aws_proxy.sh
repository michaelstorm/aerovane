#!/bin/bash
grep -v amazonaws.com /etc/hosts > hosts.tmp

# overwrite without removing while in use
cat hosts.tmp > /etc/hosts

rm hosts.tmp

host_ip=$(/sbin/ip route | awk '/default/ { print $3; }')

#echo $host_ip iam.amazonaws.com >> /etc/hosts
echo $host_ip ec2.amazonaws.com >> /etc/hosts
echo $host_ip ec2.us-east-1.amazonaws.com >> /etc/hosts
echo $host_ip ec2.us-west-1.amazonaws.com >> /etc/hosts
echo $host_ip ec2.us-west-2.amazonaws.com >> /etc/hosts
