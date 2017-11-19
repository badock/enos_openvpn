#!/usr/bin/env bash

# set -x

HOSTS_STR=""
IPS_STR=""
COUNTER=1
VIRTUAL_IP_PREFIX="11.8.0"

declare -a VIRTUAL_IPS_ARRAY


echo "#!/usr/bin/env bash" > tmp/fix_hosts_and_vips.sh
echo "LIBVIRT_CONTAINER_HOST_FILE=\$(docker inspect nova_libvirt | grep \"HostsPath\" | grep -oe \"/var/lib.*hosts\")" >> tmp/fix_hosts_and_vips.sh

echo "if [ \"\$LIBVIRT_CONTAINER_HOST_FILE\" != \"\" ]; then" >> tmp/fix_hosts_and_vips.sh

while read -r HOST
do
    IP=$(getent hosts $HOST | awk '{ print $1 }' | head -n 1)
    HOSTS_STR="$HOSTS_STR $HOST"
    IPS_STR="$IPS_STR $IP"
    VIRTUAL_IP="$VIRTUAL_IP_PREFIX.$COUNTER"
    VIRTUAL_IPS="$VIRTUAL_IP $VIRTUAL_IPS"
    VIRTUAL_IPS_ARRAY[COUNTER]=$VIRTUAL_IP

    echo "    echo \"$VIRTUAL_IP $HOST\" >> \$LIBVIRT_CONTAINER_HOST_FILE" >> tmp/fix_hosts_and_vips.sh

    ((COUNTER++))
done < tmp/uniq_hosts.txt
echo "fi" >> tmp/fix_hosts_and_vips.sh

while read HOST
do
    # IP=$(getent hosts $HOST | awk '{ print $1 }' | head -n 1)
    scp tmp/fix_hosts_and_vips.sh root@$HOST:.
    ssh $HOST -l root "bash fix_hosts_and_vips.sh" < /dev/null
done < tmp/uniq_hosts.txt

exit 0
