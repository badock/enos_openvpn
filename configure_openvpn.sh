#!/usr/bin/env bash

# Clean and create a temporary folder
# echo " * preparing tmp folder"
# if [ -d tmp ]; then
#     rm -rf tmp
# fi
# mkdir tmp

# # Upload private and public key on hosts
# cat $OAR_NODE_FILE | uniq > tmp/uniq_hosts.txt

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
    OTHER_VIRTUAL_IPS=$(echo $VIRTUAL_IPS | sed "s/$VIRTUAL_IP//g")
    OTHER_IPS_STR=$(echo $IPS_STR | sed "s/$IP//g")
    CLIENT_ID="client$COUNTER"

    echo "host: $HOST"
    echo "   IP: $IP"
    echo "   VIRTUAL_IP: $VIRTUAL_IP"
    echo "   IS_MASTER: $IS_MASTER"
    echo "   MASTER_IP: $MASTER_IP"
    echo "   OTHER_VIRTUAL_IPS: $OTHER_VIRTUAL_IPS"
    echo "   OTHER_IPS_STR: $OTHER_IPS_STR"
    echo "   CLIENT_ID: $CLIENT_ID"

    # Upload the 'openvpn_all_in_one.sh' script
    scp template/openvpn_all_in_one.sh root@$HOST:openvpn_all_in_one.sh

    # Run the 'openvpn_all_in_one.sh' script
    CMD="bash openvpn_all_in_one.sh '$VIRTUAL_IP' '$MASTER_IP' '$IS_MASTER' '$MASTER_IP' '$OTHER_VIRTUAL_IPS' '$OTHER_IPS_STR' '$CLIENT_ID'"
    #echo $CMD
    ssh -l root $HOST $CMD < /dev/null

    # Update the counter before continuing the loop
    ((COUNTER++))
done < tmp/uniq_hosts.txt

# Start the DHCP server on the master node
#ssh -l root $MASTER_IP "/etc/init.d/dnsmasq start" < /dev/null

exit 0
