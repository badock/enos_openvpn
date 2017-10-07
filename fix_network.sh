#!/usr/bin/env bash

# set -x

HOSTS_STR=""
IPS_STR=""
COUNTER=1
VIRTUAL_IP_PREFIX="192.168.1"

declare -a VIRTUAL_IPS_ARRAY

while read -r HOST
do
    IP=$(getent hosts $HOST | awk '{ print $1 }' | head -n 1)
    HOSTS_STR="$HOSTS_STR $HOST"
    IPS_STR="$IPS_STR $IP"
    VIRTUAL_IP="$VIRTUAL_IP_PREFIX.$COUNTER"
    VIRTUAL_IPS="$VIRTUAL_IP $VIRTUAL_IPS"
    VIRTUAL_IPS_ARRAY[COUNTER]=$VIRTUAL_IP
    ((COUNTER++))
done < tmp/uniq_hosts.txt

echo $HOSTS_STR
echo $IPS_STR
echo $VIRTUAL_IPS

COUNTER=1
while read HOST
do
    IP=$(getent hosts $HOST | awk '{ print $1 }' | head -n 1)
    VIRTUAL_IP=${VIRTUAL_IPS_ARRAY[$COUNTER]}
    if [ $COUNTER -eq 3 ]; then
        NETWORK_NODE_IP=$IP
    fi
    ((COUNTER++))
done < tmp/uniq_hosts.txt

if [ "$NETWORK_NODE_IP" != "" ]; then
    ssh $NETWORK_NODE_IP -l root "ip addr del 11.8.1.3/24 dev tap1; ip addr add 11.8.1.3/24 dev br-ex; ifconfig br-ex up; route add -net 11.8.1.0/24 br-ex;" < /dev/null
fi

exit 0
