#!/usr/bin/env bash

echo "Configuring TincVPN on this host"

if [ $# -ne 8 ]; then
    echo "./tinc_all_in_one.sh <LOCAL_VPN_IP> <REMOTE_WAN_IP> <IS_MASTER> <MASTER_NODE> <OTHER_VPN_IPS> <OTHER_IPS_STR> <CLIENT_ID> <COUNTER>"
    exit 1
fi

LOCAL_VPN_IP="$1"
REMOTE_WAN_IP="$2"
IS_MASTER="$3"
MASTER_NODE="$4"
OTHER_VPN_IPS="$5"
OTHER_IPS_STR="$6"
CLIENT_ID="$7"
COUNTER="$8"

#################################################
# Install Tinc
#################################################
apt-get install -y tinc screen dnsutils

#################################################
# Configure Tinc
#################################################

LOCAL_SHORT_HOSTNAME=$(hostname --short | sed 's/-//g')
MASTER_SHORT_HOSTNAME=$(nslookup $MASTER_NODE | grep name | sed 's/.*name = //g' | cut -d. -f1 | sed 's/-//g')
INTERFACE="tap0"

mkdir -p /etc/tinc/net0/hosts
mkdir -p /etc/tinc/net1/hosts

if [ "$IS_MASTER" == "TRUE" ]; then
    cat << EOF > /etc/tinc/net0/tinc.conf
Name = $LOCAL_SHORT_HOSTNAME
AddressFamily = ipv4
Interface = tap0
DeviceType = tap
# # <Multicast>
# ListenAddress = * 3501
# Address = 11.8.0.$COUNTER 3501
# Device = /dev/net/tun
# DeviceType = multicast
# # </Multicast>
#Forwarding = kernel
Mode = switch
Port = 3501
Cipher = none
#Cipher = aes-128-cbc
#UDPSndBuf = 393216
#UDPRcvBuf = 393216
PMTU = 48000
PMTUDiscovery = no
EOF
    cat << EOF > /etc/tinc/net1/tinc.conf
Name = $LOCAL_SHORT_HOSTNAME
AddressFamily = ipv4
Interface = tap1
DeviceType = tap
# # <Multicast>
# ListenAddress = * 3501
# Address = 11.8.1.$COUNTER 3502
# Device = /dev/net/tun
# DeviceType = multicast
# # </Multicast>
#Forwarding = kernel
Mode = switch
Port = 3502
Cipher = none
#Cipher = aes-128-cbc
#UDPSndBuf = 393216
#UDPRcvBuf = 393216
PMTU = 48000
PMTUDiscovery = No
EOF
else
    cat << EOF > /etc/tinc/net0/tinc.conf
Name = $LOCAL_SHORT_HOSTNAME
AddressFamily = ipv4
Interface = tap0
DeviceType = tap
# # <Multicast>
# ListenAddress = * 3501
# Address = 11.8.0.$COUNTER 3501
# Device = /dev/net/tun
# DeviceType = multicast
# # </Multicast>
#Forwarding = kernel
Mode = switch
ConnectTo = $MASTER_SHORT_HOSTNAME
Port = 3501
Cipher = none
#Cipher = aes-128-cbc
#UDPSndBuf = 393216
#UDPRcvBuf = 393216
PMTU = 48000
PMTUDiscovery = no
EOF
    cat << EOF > /etc/tinc/net1/tinc.conf
Name = $LOCAL_SHORT_HOSTNAME
AddressFamily = ipv4
Interface = tap1
DeviceType = tap
# # <Multicast>
# ListenAddress = * 3502
# Address = 11.8.1.$COUNTER 3502
# Device = /dev/net/tun
# DeviceType = multicast
# # </Multicast>
#Forwarding = kernel
Mode = switch
ConnectTo = $MASTER_SHORT_HOSTNAME
Port = 3502
Cipher = none
#Cipher = aes-128-cbc
#UDPSndBuf = 393216
#UDPRcvBuf = 393216
PMTU = 48000
PMTUDiscovery = no
EOF
fi

if [ "$IS_MASTER" == "TRUE" ]; then
    MASTER_PUBLIC_ADDRESS=$(ping $MASTER_NODE -c 1 | grep -o -E '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1)
    cat << EOF > /etc/tinc/net0/hosts/$LOCAL_SHORT_HOSTNAME
Address = $MASTER_PUBLIC_ADDRESS 3501
Subnet = 11.8.0.$COUNTER/32
EOF
    cat << EOF > /etc/tinc/net1/hosts/$LOCAL_SHORT_HOSTNAME
Address = $MASTER_PUBLIC_ADDRESS 3502
Subnet = 11.8.1.$COUNTER/32
EOF
else
    cat << EOF > /etc/tinc/net0/hosts/$LOCAL_SHORT_HOSTNAME
Subnet = 11.8.0.$COUNTER/32
EOF
    cat << EOF > /etc/tinc/net1/hosts/$LOCAL_SHORT_HOSTNAME
Subnet = 11.8.1.$COUNTER/32
EOF
fi

tincd -n net0 -K4096
tincd -n net1 -K4096

cat << EOF > /etc/tinc/net0/tinc-up
ifconfig tap0 11.8.0.$COUNTER netmask 255.255.255.0 mtu 4800
EOF
cat << EOF > /etc/tinc/net1/tinc-up
ifconfig tap1 11.8.1.$COUNTER netmask 255.255.255.0 mtu 4800
EOF

cat << EOF > /etc/tinc/net0/tinc-down
ifconfig tap0 11.8.0.$COUNTER netmask down
EOF
cat << EOF > /etc/tinc/net1/tinc-down
ifconfig tap1 11.8.1.$COUNTER netmask down
EOF

chmod 755 /etc/tinc/net0/tinc-*
chmod 755 /etc/tinc/net1/tinc-*

cat << EOF > /etc/tinc/nets.boot
net0
net1
EOF

# #################################################
# # Run Tinc
# #################################################
# service tinc stop
# service tinc start
# service tinc restart

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

apt-get install -y bridge-utils

brctl addbr docker0
ip addr add 192.168.42.1/24 dev docker0
ip link set dev docker0 up
ip addr show docker0
#systemctl restart docker
iptables -t nat -L -n

exit 0
EOF

bash /root/create_docker0.sh

#################################################
# FIX: Configure network
#################################################
sh -c 'echo 1 > /proc/sys/net/ipv4/ip_forward'
iptables -t nat -A POSTROUTING -s 11.8.0.0/24 -o eth0 -j MASQUERADE
iptables -t nat -A POSTROUTING -s 11.8.1.0/24 -o eth0 -j MASQUERADE

# br-ex     Link encap:Ethernet  HWaddr 52:ae:99:dd:5d:49
# inet addr:11.8.1.3  Bcast:0.0.0.0  Mask:255.255.255.0
# inet6 addr: fe80::50ae:99ff:fedd:5d49/64 Scope:Link
# UP BROADCAST RUNNING MULTICAST  MTU:48000  Metric:1
# RX packets:13 errors:0 dropped:0 overruns:0 frame:0
# TX packets:8 errors:0 dropped:0 overruns:0 carrier:0
# collisions:0 txqueuelen:0
# RX bytes:990 (990.0 B)  TX bytes:648 (648.0 B)

exit 0
