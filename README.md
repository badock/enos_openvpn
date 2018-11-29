# Enos OpenVPN

## Description

Deploy an OpenStack infrastructure via Enos, in which the management network and the production network are implemented with two OpenVPN networks.

## Installation

clone the project:

```
git clone https://github.com/badock/enos_openvpn.git
```

## Deploy OpenStack

### Configure the hosts that will be used

Put the servers' addresses in the tmp/uniq_hosts.txt, as follow:

``` bash
jpastor@fnantes:~/enos_openvpn$ cat tmp/uniq_hosts.txt 
econome-20.nantes.grid5000.fr
econome-21.nantes.grid5000.fr
econome-22.nantes.grid5000.fr
econome-3.nantes.grid5000.fr
econome-4.nantes.grid5000.fr
```

*Ensure that you can connect as root via SSH on each of these server.*

Then run configure the nodes so that they can connect to each other:
``` bash
bash configure_ssh_connections.sh
```

### Configure a network


You can setup the VPN network via OpenVPN (centralized) or Tinc (decentralized).

#### OpenVPN

``` bash
bash configure_openvpn.sh
```

#### Tinc

``` bash
bash configure_tinc.sh
```

### Configure enos

We need to create a Python virtual environment on a service node, install enos and its dependencies and configure a reservation.yaml file for enos.

#### reservation.yaml file

Configure the reservation.yaml that uses the [*static*](https://enos.readthedocs.io/en/stable/provider/static.html) provider. You have to specify the nodes of your infrastructure (controllers nodes, network nodes, compute nodes) in the reservation.yaml file. Keep in mind that the IP addresses should be IPs of the management, which by convention is "11.8.0.0/24".

#### Configure a service node

``` bash
bash configure_enos.sh
```

### Run Enos

Once all the previous steps have been *successfully* completed, simply run the following command:

``` bash
bash run_enos.sh
```

### (Bonus) fix live migrations

To enable live migrations, the hosts files of nova-libvirt containers must contain the addresses of all compute nodes of the OpenStack infrastructure that you deployed.

To do so, run the following script:

``` bash
bash fix_live_migration.sh
```


