# Enos OpenVPN

## Description

Deploy an OpenStack infrastructure via Enos, in which the management network and the production network are implemented with two OpenVPN networks.

```
          +-------------------------------------------------------------------------------------+
          |                                ENOS/                                                |
   MINIMUM|        MASTER                  OPENVPN_NODE               CONTROL        NET.       |
   INSTALL|   +--------------+            +-----------+              +-------+     +-------+    |
          |   |              |            |           |              |       |     |       |    |
          |   |              |            |           |              |       |     |       |    |
          |   | enos openvpn |            |           |              |       |     |       |    |
          |   |              |            |           |              +-------+     +-------+    |
          |   |              |            |           |                         +---------------+
          |   |              |            +-----------+                C1       |
          |   |              |                                       +-------+  |
          |   +--------------+                                       |       |  |
          |               ^                                          |       |  |
          |               |                                          |       |  |
          |               |                                          +-------+  |
          |               |                                                     |
          +---------------------------------------------------------------------+
                          |
                          |                           x.x.x.x
                          |                          +-------+
                          |                          |       |
	                  +--------------------------+       |
                              request addition       |       |
                                 to openvpn          +-------+
                               and openstack
```

## TLDR;

Put the addresses of your servers in a *current/hosts* file (**not /tmp**), and run

``` bash
python eov.py deploy && python eov.py openvpn && python eov.py enos
```

## Installation

Clone the project:

```
git clone https://github.com/badock/enos_openvpn.git
```

## Basic configuration

You can use running machines (just below) or get some resources and deploy on g5k using the deploy command (second part)

### Configure the hosts that will be used (without g5k)

Put the servers' addresses in the *current/hosts* as follow:

``` bash
jpastor@fnantes:~/enos_openvpn$ cat current/hosts
econome-20.nantes.grid5000.fr
econome-21.nantes.grid5000.fr
econome-22.nantes.grid5000.fr
econome-3.nantes.grid5000.fr
econome-4.nantes.grid5000.fr
```

**Ensure that you can connect as root via SSH on each of these server.**

### Get resources and deploy everything needed on g5k

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


### OpenVPN

``` bash
Usage: eov openvpn

Deploy openvpn on resources from current/hosts
```

## Configure enos

We need to create a Python virtual environment on a service node, install enos and its dependencies and configure a reservation.yaml file for enos.

#### reservation.yaml file

Configure the reservation.yaml that uses the [*static*](https://enos.readthedocs.io/en/stable/provider/static.html) provider. You have to specify the nodes of your infrastructure (controllers nodes, network nodes, compute nodes) in the reservation.yaml file. Keep in mind that the IP addresses should be IPs of the management, which by convention is "11.8.0.0/24".

## Run Enos

Once all the previous steps have been **successfully** completed, simply run the following command:

``` bash
Usage: eov enos [options]

Deploy enos on hosts

Options:
    --g5k              Deploying on g5k [default: false]

```

## (Bonus) fix live migrations

To enable live migrations, the hosts files of nova-libvirt containers must contain the addresses of all compute nodes of the OpenStack infrastructure that you deployed.

To do so, run the following script:

``` bash
bash fix_live_migration.sh
```

## Add a node


On the node where you deployed enos openvpn, use
``` bash
export FLASK_APP=eov.py
flask run --host=0.0.0.0
```
This allows to accept requests from other nodes.

Run the node normally. To get one on g5k, you can use for example:
``` bash
oarsub -I -l nodes=1,walltime=<TIME_OF_NODE_RUNNING> -p "cluster='<CLUSTER>'" -t deploy
kadeploy3 -e debian9-x64-nfs -f $OAR_NODE_FILE -k
```
Then ssh on it.

If the node is not on g5k, you will need to get the public key from the "master" node:
``` bash
curl http://<MASTER_IP>:5000/ >> .ssh/authorized_keys
```
This will get the public key from the master node and add it to autorized keys.

Then, you just have to request to be added to the openstack with
``` bash
http://<MASTER_IP>:5000/addnode/<G5K>/<NODE_IP>
```
Where:
* `MASTER_IP` is the ip of the master node (where you have ran enos openvpn, you can get it with `ip a` on the master node).
* `G5K` is a boolean (True or False), whether the node is on g5k or not
* `NODE_IP` is the ip of the node you want to add
