#!/usr/bin/env bash

set -x

echo "Configuring OpenVPN on this host"

if [ $# -ne 7 ]; then
    echo "./configure_vpn.sh <LOCAL_VPN_IP> <REMOTE_WAN_IP> <IS_MASTER> <MASTER_NODE> <OTHER_VPN_IPS> <OTHER_IPS_STR> <CLIENT_ID>"
    exit 1
fi

LOCAL_VPN_IP="$1"
REMOTE_WAN_IP="$2"
IS_MASTER="$3"
MASTER_NODE="$4"
OTHER_VPN_IPS="$5"
OTHER_IPS_STR="$6"
CLIENT_ID="$7"

#################################################
# Install OpenVPN
#################################################
apt-get install -y openvpn screen bridge-utils

#################################################
# Configure OpenVPN
#################################################
if [ "$IS_MASTER" == "TRUE" ]; then
    openvpn --genkey --secret /etc/openvpn/openvpn-shared-key.key
else
    scp $MASTER_NODE:/etc/openvpn/openvpn-shared-key.key /etc/openvpn/openvpn-shared-key.key
fi

if grep -q nobody /etc/group
    then
         echo "group nobody already exists"
    else
         echo "group nobody does not exist";
         groupadd nobody
fi


if [ ! -d "/etc/openvpn" ]; then
    mkdir -p /etc/openvpn
fi


if [ ! -d "/etc/openvpn/keys" ]; then
    mkdir -p /etc/openvpn/keys
fi

# Configure OpenVPN as a systemd service
if [ "$IS_MASTER" == "TRUE" ]; then
    # Block executed by master node

    # Configure network
    sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'
    iptables -t nat -A POSTROUTING -s 11.8.0.0/24 -o eno1 -j MASQUERADE
    iptables -t nat -A POSTROUTING -s 11.8.1.0/24 -o eno1 -j MASQUERADE

    # Generating keys
    cp -r /usr/share/easy-rsa/ /etc/openvpn
    chown -R $USER /etc/openvpn/easy-rsa/

    ln -s /etc/openvpn/easy-rsa/openssl-1.0.0.cnf /etc/openvpn/easy-rsa/openssl.cnf

    pushd /etc/openvpn/easy-rsa/
    source vars
    ./clean-all
    ./build-dh
    ./pkitool --initca
    ./pkitool --server server
    openvpn --genkey --secret keys/ta.key

    cp keys/ca.crt keys/ta.key keys/server.crt keys/server.key keys/dh2048.pem /etc/openvpn/
    mkdir /etc/openvpn/jail
    mkdir /etc/openvpn/jail/tmp
    mkdir /etc/openvpn/clientconf
    mkdir /etc/openvpn/server
    popd

    cat << EOF > /etc/openvpn/server.conf
# Serveur TCP/443
mode server
tls-server
#proto tcp
proto udp
port 443
dev tap

# # Clés et certificats
ca ca.crt
cert server.crt
key server.key
dh dh2048.pem
tls-auth ta.key 0
#cipher AES-256-CBC
#secret /etc/openvpn/openvpn-shared-key.key

# Réseau
server 11.8.0.0 255.255.255.0
client-to-client
#push "route 11.8.0.0 255.255.255.0"
push "route 255.255.255.255 255.255.255.255"

#On définit le serveur VPN comme passerelle par défaut pour les clients.
#push "redirect-gateway bypass-dhcp"

push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 8.8.8.8"
push "dhcp-option DNS 8.8.4.4"
keepalive 10 120

# Sécurite
user nobody
group nogroup
chroot /etc/openvpn/jail
persist-key
persist-tun

# Log
verb 3
mute 20
status openvpn-status.log
log-append /var/log/openvpn.log

# Tweak
sndbuf 393216
rcvbuf 393216
push "sndbuf 393216"
push "rcvbuf 393216"
tun-mtu 48000
fragment 0
mssfix 0
#cipher aes-256-cbc
#cipher none
cipher AES-128-CBC
#engine aesni
#comp-lzo
EOF

    cat << EOF > /etc/openvpn/server2.conf
# Serveur TCP/444
mode server
tls-server
#proto tcp
proto udp
port 444
dev tap

# # Clés et certificats
ca ca.crt
cert server.crt
key server.key
dh dh2048.pem
tls-auth ta.key 0
#cipher AES-256-CBC
#secret /etc/openvpn/openvpn-shared-key.key

# Réseau
server 11.8.1.0 255.255.255.0
client-to-client
#push "route 11.8.1.0 255.255.255.0"
push "route 255.255.255.255 255.255.255.255"

#On définit le serveur VPN comme passerelle par défaut pour les clients.
#push "redirect-gateway bypass-dhcp"

push "redirect-gateway def1 bypass-dhcp"
push "dhcp-option DNS 8.8.8.8"
push "dhcp-option DNS 8.8.4.4"
keepalive 10 120

# Sécurite
user nobody
group nogroup
chroot /etc/openvpn/jail
persist-key
persist-tun

# Log
verb 3
mute 20
status openvpn-status.log
log-append /var/log/openvpn.log

# Tweak
sndbuf 393216
rcvbuf 393216
push "sndbuf 393216"
push "rcvbuf 393216"
tun-mtu 48000
fragment 0
mssfix 0
#cipher aes-256-cbc
#cipher none
cipher AES-128-CBC
#engine aesni
#comp-lzo
EOF

else
    # Block executed by slave nodes
    pkill openvpn

    ssh -l root $MASTER_NODE "cd /etc/openvpn/easy-rsa; source vars; ./pkitool $CLIENT_ID #./build-key $CLIENT_ID"
    ssh -l root $MASTER_NODE "mkdir -p /etc/openvpn/clientconf/$CLIENT_ID/"
    ssh -l root $MASTER_NODE "cp /etc/openvpn/ca.crt /etc/openvpn/ta.key /etc/openvpn/easy-rsa/keys/$CLIENT_ID.crt /etc/openvpn/easy-rsa/keys/$CLIENT_ID.key /etc/openvpn/clientconf/$CLIENT_ID/"

    cat << EOF > client.conf
# Client
client
tls-client
dev tap
#proto tcp-client
proto udp
remote $MASTER_NODE 443
resolv-retry infinite
#cipher AES-256-CBC

# Clés
ca ca.crt
cert $CLIENT_ID.crt
key $CLIENT_ID.key
tls-auth ta.key 1

# Sécurite
nobind
persist-key
persist-tun
verb 3

script-security 2
route-up /root/delete_route.sh

# Tweak
tun-mtu 48000
fragment 0
mssfix 0
#cipher aes-256-cbc
#cipher none
cipher AES-128-CBC
#comp-lzo
EOF

    cat << EOF > client1.conf
# Client
client
tls-client
dev tap
#proto tcp-client
proto udp
remote $MASTER_NODE 444
resolv-retry infinite
#cipher AES-256-CBC

# Clés
ca ca.crt
cert $CLIENT_ID.crt
key $CLIENT_ID.key
tls-auth ta.key 1

# Sécurite
nobind
persist-key
persist-tun
verb 3

script-security 2
route-up /root/delete_route.sh

# Tweak
tun-mtu 48000
fragment 0
mssfix 0
#cipher aes-256-cbc
#cipher none
cipher AES-128-CBC
#comp-lzo
EOF

    cat << EOF > /root/delete_route.sh
#!/usr/bin/env bash
#/sbin/ip route del 128.0.0.0/1 || true
exit 0
EOF
    chmod +x /root/delete_route.sh

    scp client.conf root@$MASTER_NODE:/etc/openvpn/clientconf/$CLIENT_ID/client.conf
    scp client1.conf root@$MASTER_NODE:/etc/openvpn/clientconf/$CLIENT_ID/client1.conf

    ssh -l root $MASTER_NODE "cd /etc/openvpn/clientconf; tar -zcvf $CLIENT_ID.tgz $CLIENT_ID"
    scp root@$MASTER_NODE:/etc/openvpn/clientconf/$CLIENT_ID.tgz client.tgz

    tar -zxvf client.tgz

    screen -dmS openvpn_screen bash -c "pushd $CLIENT_ID; openvpn client.conf; popd"
    sleep 1
    screen -dmS openvpn_screen bash -c "pushd $CLIENT_ID; openvpn client1.conf; popd"
fi


#################################################
# Start OpenVPN service
#################################################
# systemctl enable openvpn
# systemctl start openvpn
# systemctl restart openvpn
openvpn --daemon ovpn-server --status /run/openvpn/server.status 10 --cd /etc/openvpn --config /etc/openvpn/server.conf
openvpn --daemon ovpn-server --status /run/openvpn/server.status 10 --cd /etc/openvpn --config /etc/openvpn/server2.conf


#if [ "$IS_MASTER" == "TRUE" ]; then
    iptables -t nat -A POSTROUTING -s 11.8.0.0/24 -o eno1 -j MASQUERADE
    iptables -t nat -A POSTROUTING -s 11.8.1.0/24 -o eno1 -j MASQUERADE
#fi


# #################################################
# # Install and configure a DHCP server
# #################################################
# if [ "$IS_MASTER" == "TRUE" ]; then
#     #http://blog.lincoln.hk/blog/2013/05/17/softether-on-vps-using-local-bridge/
#     # Install dnsmasq
#     apt-get install -y dnsmasq
#     # Setup dnsmask to handle tap0
#     cat << EOF >> /etc/dnsmasq.conf
# interface=tap1
# dhcp-range=tap1,11.8.1.50,11.8.1.200,12h
# dhcp-option=tap1,3,11.8.1.1
# EOF
#     # Restart dnsmasq in order to use the new configuration
#     /etc/init.d/dnsmasq stop
# fi

#################################################
# FIX: create manually the Docker0 interface
#################################################
cat << EOF > /root/create_docker0.sh
#!/bin/bash

#
# create docker0 bridge
# restart docker systemd service
# confirm new outgoing NAT masquerade is set up
#
# reference
#     https://docs.docker.com/engine/userguide/networking/default_network/build-bridges/
#

brctl addbr docker0
ip addr add 192.168.42.1/24 dev docker0
ip link set dev docker0 up
ip addr show docker0
#systemctl restart docker
iptables -t nat -L -n

exit 0
EOF

bash /root/create_docker0.sh

exit 0
