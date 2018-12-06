#!/usr/bin/env bash

# set -x

# # Clean and create a temporary folder
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
G5K_PARTITION_SIZE_FIX="true"

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

    ssh $IP -l root "screen -dmS install_python bash -c 'apt-get install -y python python-dev git python-pip; echo 1 > /root/python_install_done.txt'" < /dev/null

    if [ "$G5K_PARTITION_SIZE_FIX" = "true" ]; then
        echo "/!\ Warning: G5K_PARTITION_SIZE_FIX should be true only for Grid'5000."
	echo "Creating docker volumes directory in /tmp"
	ssh $IP -l root "mkdir -p /tmp/docker/volumes" < /dev/null
	ssh $IP -l root "mkdir -p /var/lib/docker/volumes" < /dev/null
	ssh $IP -l root "(mount | grep /tmp/docker/volumes) || mount --bind /tmp/docker/volumes /var/lib/docker/volumes" < /dev/null

	echo "Creating nova directory in /tmp"
	ssh $IP -l root "mkdir -p /tmp/nova" < /dev/null
	ssh $IP -l root "mkdir -p /var/lib/nova" < /dev/null
	ssh $IP -l root "(mount | grep /tmp/nova) || mount --bind /tmp/nova /var/lib/nova" < /dev/null
    fi


    # Update the counter before continuing the loop
    ((COUNTER++))
done < tmp/uniq_hosts.txt

while read HOST
do
    IP=$(getent hosts $HOST | awk '{ print $1 }' | head -n 1)
    FILE_CONTENT=$(ssh -l root $IP "cat /root/python_install_done.txt" < /dev/null)

    while [ "$FILE_CONTENT" != "1" ]; do
        FILE_CONTENT=$(ssh -l root $IP "cat /root/python_install_done.txt" < /dev/null)
        echo "waiting 10 seconds for $IP"
        sleep 10
    done

    echo "Python has been installed on $IP"
done < tmp/uniq_hosts.txt

if [ "$MASTER_IP" != "" ]; then
    ## ssh $MASTER_IP -l root "pip install --upgrade cffi" < /dev/null
    # ssh $MASTER_IP -l root "apt-get install -y libpq-dev python-dev libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev libffi-dev" < /dev/null
    # ssh $MASTER_IP -l root "pip install --upgrade cffi" < /dev/null
    # ssh $MASTER_IP -l root "pip install enos" < /dev/null

    ssh $MASTER_IP -l root "pip install virtualenv" < /dev/null
    ssh $MASTER_IP -l root "virtualenv enos_env" < /dev/null
    # ssh $MASTER_IP -l root ". enos/bin/activate; pip install enos" < /dev/null
    ssh $MASTER_IP -l root ". enos_env/bin/activate; git clone https://github.com/beyondtheclouds/enos.git -b stable/queens; pip install -e enos/" < /dev/null

    scp reservation.yaml root@$MASTER_IP:.
fi

exit 0
