#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enos OpenVPN launches enos with a VPN

Usage:
  eov [-h|--help] <command> [<args>...]

General options:
  -h --help           Show this help message.

Commands:
  deploy [<args>...]  Claim resources from g5k and deploy debian
  openvpn             Deploy OpenVPN on resources
  enos                Deploy enos
  cleanup             Cleans the current experiment directory

See 'eov command --help' for more information
on a specific command.

"""

import os
import shutil
import sys
import logging
import yaml
import time

from docopt import docopt
from flask import Flask
import execo
import execo_g5k as ex5
import execo_g5k.api_utils as api
from enoslib.api import run_ansible

from utils import (EOV_PATH, ANSIBLE_PATH, SYMLINK_NAME, doc,
doc_lookup)


# Formatting the logger

logger = logging.getLogger('logger')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# Creating a Flask instance

app = Flask(__name__)

@doc()
def deploy(xp_name, walltime, cluster, nodes, reservation=None, **kwargs):
    """
usage: eov deploy [options]

Claim resources from G5k and deploy debian

Options:
    -n, --xp-name NAME               Name of the experiment [default: enos_openvpn]
    -w, --walltime WALLTIME          Length, in time, of the experiment [default: 08:00:00]
    -c, --cluster CLUSTER            Cluster to deploy onto [default: ecotype]
    -r, --reservation RESERVATION    When to make the reservation (format is 'yyyy-mm-dd hh:mm:ss')
    --nodes NUMBER                   Number of nodes [default: 5]

    """
    existing_jobs = ex5.oargrid.get_current_oargrid_jobs()
    # Getting an existing job
    for oargridjob in existing_jobs:
        oarjobs = ex5.oargrid.get_oargrid_job_oar_jobs(oargridjob)
        for oarjob in oarjobs:
            info = ex5.oar.get_oar_job_info(oar_job_id=oarjob[0],
                                            frontend=oarjob[1])
            if info["name"] == xp_name:
                job = oargridjob
    if not 'job' in locals():
        logging.info("Making a submission")
        job_specs = [(ex5.OarSubmission(resources="nodes="+nodes,
                                        walltime=walltime,
                                        reservation_date=reservation,
                                        job_type="deploy",
                                        name=xp_name), cluster)]
        logging.info("Getting job %s on %s nodes of %s cluster" \
                     " for %s hours" % (xp_name, nodes, cluster, walltime))
        if reservation:
            logging.info("With the reservation parameter: %s" % reservation)
        job, _ = ex5.oargridsub(job_specs,
                                walltime=walltime,
                                reservation_date=reservation,
                                job_type="deploy")
        if job is None:
            raise Exception("Can not get a job, check the parameters")
        logging.info("Waiting for oargridjob %s to start" % job)
        ex5.wait_oargrid_job_start(job)
    nodes = ex5.get_oargrid_job_nodes(job)
    hosts_file = 'current/hosts'
    if not (os.path.exists(hosts_file) and
    os.path.isfile(hosts_file) and
    os.stat(hosts_file).st_size == 0):
        logging.info("Deploying debian on nodes %s" % nodes)
        deployment = ex5.kadeploy.Deployment(hosts=nodes,
                                             env_name='debian9-x64-nfs')
        deployed, undeployed = ex5.kadeploy.deploy(deployment)
        logging.info("Deployed debian on: %s" % ', '.join(map(str, deployed)))
        if undeployed:
            logging.warning("Deployment did not work on: %s" % ', '.join(map(str, deployed)))
        with open(hosts_file, 'w') as f:
            for host in deployed:
                f.write("%s\n" % host)


@doc()
def openvpn(add=None, **kwargs):
    """
Usage: eov openvpn [options]

Deploy openvpn on resources from current/hosts

Options:
    --add NODE         Add defined node
    """
    hosts_file = 'current/hosts'
    if not (os.path.exists(hosts_file) and
    os.path.isfile(hosts_file) and
    os.stat(hosts_file).st_size == 0):
        if add:
            with open(hosts_file, 'a') as f:
                logging.info("Adding %s to host file" % add)
                f.write('\n%s' % add)
        hosts = [host.strip() for host in open("current/hosts", 'r')]
        logging.info("Running ansible")
        exec_dir = os.path.dirname(os.path.realpath(__file__))
        extra_vars = { 'exec_dir': exec_dir ,
                       'nodes': hosts,
                       'addition': add }
        launch_playbook = os.path.join(ANSIBLE_PATH, 'openvpn.yml')
        run_ansible([launch_playbook], 'current/hosts',
                    extra_vars=extra_vars)
    else:
        logging.error("No host to run onto.")


# pip target is bugged, so for now, enos dir will be in /tmp/src
# https://github.com/pypa/pip/issues/4390
@doc()
def enos(g5k, enos_dir, add=None, **kwargs):
    """
Usage: eov enos [options]

Deploy enos on hosts

Options:
    --g5k              Deploying on g5k [default: false]
    --add NODE         Add defined node
    --enos_dir DIR     Define enos install directory [default: /tmp/src]

    """
    hosts_file = 'current/hosts'
    extra_vars = { 'g5k': g5k,
                   'enos_dir': enos_dir}
    if not (os.path.exists(hosts_file) and
    os.path.isfile(hosts_file) and
    os.stat(hosts_file).st_size == 0):
        if add:
            with open(hosts_file) as f:
                if not (add in line for line in f):
                    logging.warning("Adding %s to host file, "\
                                    "did you ran openvpn?" % add)
                    f.write('\n%s' % add)
            alias, address = _add_node_in_reservation(add)
            _add_node_in_multinode(alias, address)
            add = alias
        hosts = [host.strip() for host in open(hosts_file, 'r')]
        logging.info("Running ansible")
        exec_dir = os.path.dirname(os.path.realpath(__file__))
        extra_vars.update({'exec_dir': exec_dir,
                           'nodes': hosts,
                           'addition': add})
        launch_playbook = os.path.join(ANSIBLE_PATH, 'enos.yml')
        run_ansible([launch_playbook], 'current/hosts',
                    extra_vars=extra_vars)
    else:
        logging.error("No host to run onto.")


def _add_node_in_reservation(add):
    current_nodes = 'current/reservation.yaml'
    if not (os.path.exists(current_nodes) and
    os.path.isfile(current_nodes)):
        shutil.copy2('reservation.yaml',
                     'current/reservation.yaml')
    node_present = False
    with open(current_nodes, "r") as f:
        for line in f:
            if add in line:
                node_present = True
    with open(current_nodes, "r") as f:
        reservation = yaml.load(f)
    if node_present:
        for compute in reservation['resources']['compute']:
            if 'node' in compute and compute['node'] == add:
                return compute['alias'], compute['address']
    all_computes = []
    for compute in reservation['resources']['compute']:
	number = int(compute['alias'].replace('compute-node', ''))
        all_computes.append(number)
    number_of_computes = max(all_computes)
    # we need a new compute node.
    #its number is the number of node plus one
    alias = 'compute-node%d' % (number_of_computes + 1)
    # its address is the same but the computes addresses start at 4
    address = '11.8.0.%d' % (number_of_computes+4)
    new_node = {'alias': alias,
                'user': 'root',
                'address': address,
                'node': str(add)}
    logging.info("Adding new node for %s: %s" % (add, new_node))
    reservation['resources']['compute'].append(new_node)
    with open(current_nodes, 'w') as f:
        yaml.dump(reservation, f)
    return alias, address


def _add_node_in_multinode(alias, address):
    multinode_file = 'current/multinode'
    # putting every line in a list
    try:
        with open(multinode_file) as f:
            lines = f.readlines()
    except:
        logging.error("Could not read file %s" % multinode_file)
    # removing all lines with compute-nodes
    multinode_no_compute = []
    for line in lines:
        if not line.startswith('compute-node'):
            multinode_no_compute.append(line)
    # adding new node
    multinode_final = []
    node_line = """%s ansible_host=%s ansible_ssh_user=root ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' network_interface=tap0 enos_devices="['tap0']"\n""" % (alias, address)
    for line in multinode_no_compute:
        multinode_final.append(line)
        if line.startswith('[compute]') or line.startswith('[default_group]'):
            multinode_final.append(node_line)
    # putting everything back into the file
    with open(multinode_file, 'w') as f:
        for line in multinode_final :
            f.write("%s" % line)


@doc()
def cleanup(**kwargs):
    """
Usage: eov cleanup

Remove everything in the current directory
    """
    shutil.rmtree('current')
    os.makedirs('current')


@app.route('/')
def ssh_public_key():
    public_key_path = '%s/.ssh/id_rsa.pub' % os.path.expanduser("~")
    with open(public_key_path) as f:
        lines = f.readlines()
    return lines[0]


@app.route('/addnode/<g5k>/<add>')
def add_node(g5k, add):
    openvpn(add)
    enos(g5k=g5k, enos_dir='/tmp/src', add=add)
    return 'You have been added' % add

@doc()
def help(**kwargs):
    """
Usage: eov help

Show the help message
    """
    print(__doc__)


if __name__ == '__main__':
    args = docopt(__doc__,
                  version='Enos OpenVPN version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
