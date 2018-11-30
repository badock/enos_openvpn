#!/usr/bin/env bash

set -eu
set -x

echo "---------------------------------"
echo "- Configuring ssh keys on hosts -"
echo "---------------------------------"

# Clean and create a temporary folder
# echo " * preparing tmp folder"
# if [ -d tmp ]; then
#     rm -rf tmp
# fi
# mkdir tmp

# Remove existing keys
rm tmp/id_rsa
rm tmp/id_rsa.pub

# Generate an ssh key
echo " * generating an ssh key"
ssh-keygen -t rsa -b 4096 -C "comment" -P "" -f tmp/id_rsa -q

# Upload private and public key on hosts
# cat $OAR_NODE_FILE | uniq > tmp/uniq_hosts.txt
while read HOST
do
    echo " * configuring $HOST"
    scp tmp/id_rsa root@$HOST:.ssh/id_rsa
    scp tmp/id_rsa.pub root@$HOST:.ssh/id_rsa.pub
    ssh root@$HOST "cat .ssh/id_rsa.pub >> .ssh/authorized_keys" < /dev/null
    while read HOST2
    do
        echo " * adding $HOST2's RSA key fingerprint to $HOST"
        IP_ADDRESS2=$(getent hosts $HOST2 | awk '{ print $1 }' | head -n 1)
        SHORT_HOSTNAME2=$(ssh root@$HOST2 'DOMAIN_NAME=$(dnsdomainname); hostname | sed "s/.$DOMAIN_NAME//g"' < /dev/null)
        ssh root@$HOST "ssh-keyscan -t rsa -H $HOST2 >> /root/.ssh/known_hosts" < /dev/null
        ssh root@$HOST "ssh-keyscan -t rsa -H $SHORT_HOSTNAME2 >> /root/.ssh/known_hosts" < /dev/null
        ssh root@$HOST "ssh-keyscan -t rsa -H $IP_ADDRESS2 >> /root/.ssh/known_hosts" < /dev/null
        echo "   -> OK"
    done < tmp/uniq_hosts.txt
    echo "   -> OK"
done < tmp/uniq_hosts.txt

exit 0
