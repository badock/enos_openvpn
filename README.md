# Enos OpenVPN

## Description

Deploy an OpenStack infrastructure via Enos, in which the management network and the production network are implemented with two OpenVPN networks.

## TLDR;

Put the addresses of your servers in a *current/hosts file* (**not /tmp**), and run

``` bash
bash configure_ssh_connections.sh && bash configure_openvpn.sh && bash configure_enos.sh && bash run_enos.sh
```

## Installation

clone the project:

```
git clone https://github.com/badock/enos_openvpn.git
```

## Deploy OpenStack

### Configure the hosts that will be used

Put the servers' addresses in the tmp/uniq_hosts.txt, as follow:

``` bash
jpastor@fnantes:~/enos_openvpn$ cat current/hosts
econome-20.nantes.grid5000.fr
econome-21.nantes.grid5000.fr
econome-22.nantes.grid5000.fr
econome-3.nantes.grid5000.fr
econome-4.nantes.grid5000.fr
```

**Ensure that you can connect as root via SSH on each of these server.**

If you are using grid5000, use the *deploy* command to prepare the hosts.
``` bash
usage: eov deploy [options]

Claim resources from G5k and launch the deployment

Options:
    -n, --xp-name NAME               Name of the experiment [default: enos_openvpn]
    -w, --walltime WALLTIME          Length, in time, of the experiment [default: 08:00:00]
    -c, --cluster CLUSTER            Cluster to deploy onto [default: ecotype]
    -r, --reservation RESERVATION    When to make the reservation (format is 'yyyy-mm-dd hh:mm:ss')
    --nodes NUMBER                   Number of nodes [default: 5]
```


#### OpenVPN

``` bash
Usage: eov openvpn

Deploy openvpn on resources from current/hosts
```

### Configure enos

We need to create a Python virtual environment on a service node, install enos and its dependencies and configure a reservation.yaml file for enos.

#### reservation.yaml file

Configure the reservation.yaml that uses the [*static*](https://enos.readthedocs.io/en/stable/provider/static.html) provider. You have to specify the nodes of your infrastructure (controllers nodes, network nodes, compute nodes) in the reservation.yaml file. Keep in mind that the IP addresses should be IPs of the management, which by convention is "11.8.0.0/24".

### Run Enos

Once all the previous steps have been **successfully** completed, simply run the following command:

``` bash
Usage: eov enos [options]

Deploy enos on hosts

Options:
    --g5k              Deploying on g5k [default: false]

```

### (Bonus) fix live migrations

To enable live migrations, the hosts files of nova-libvirt containers must contain the addresses of all compute nodes of the OpenStack infrastructure that you deployed.

To do so, run the following script:

``` bash
bash fix_live_migration.sh
```
