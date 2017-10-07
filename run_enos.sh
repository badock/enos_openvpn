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
    if [ $COUNTER -eq 1 ]; then
        IS_MASTER="TRUE"
        MASTER_IP=$IP
    else
        IS_MASTER="FALSE"
    fi
    ((COUNTER++))
done < tmp/uniq_hosts.txt

if [ "$MASTER_IP" != "" ]; then
    ssh $MASTER_IP -l root ". enos_env/bin/activate; enos deploy" < /dev/null
fi

exit 0
