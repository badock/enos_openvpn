#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Enos OpenVPN launches enos with a VPN

Usage:
  eov [-h|--help] <command> [<args>...]

General options:
  -h --help           Show this help message.

Commands:
  deploy [<args>...]  Launch Enos OpenVPN
  openvpn             Deploy OpenVPN
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
import execo
import execo_g5k as ex5
import execo_g5k.api_utils as api
from enoslib.api import run_ansible

from utils import (EOV_PATH, ANSIBLE_PATH, SYMLINK_NAME, doc,
doc_lookup)


# Formatting the logger

logger = logging.getLogger('logger')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%d-%b-%y %H:%M:%S')


@doc()
def deploy(xp_name, walltime, cluster, nodes, reservation=None, **kwargs):
    """
usage: eov deploy [options]

Claim resources from G5k and launch the deployment

Options:
    -n, --xp-name NAME               Name of the experiment [default: enos_openvpn]
    -w, --walltime WALLTIME          Length, in time, of the experiment [default: 08:00:00]
    -c, --cluster CLUSTER            Cluster to deploy onto [default: ecotype]
    -r, --reservation RESERVATION    When to make the reservation
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
def openvpn(**kwargs):
    """
Usage: eov openvpn

Deploy openvpn
    """
    hosts_file = 'current/hosts'
    if not (os.path.exists(hosts_file) and
    os.path.isfile(hosts_file) and
    os.stat(hosts_file).st_size == 0):
        hosts = [host.strip() for host in open("current/hosts", 'r')]
        logging.info("Running ansible")
        exec_dir = os.path.dirname(os.path.realpath(__file__))
        extra_vars = { 'exec_dir': exec_dir ,
                       'nodes': hosts}
        launch_playbook = os.path.join(ANSIBLE_PATH, 'openvpn.yml')
        run_ansible([launch_playbook], 'current/hosts',
                    extra_vars=extra_vars)
    else:
        logging.error("No host to run onto.")


@doc()
def enos(g5k, **kwargs):
    """
Usage: eov enos [options]

Deploy enos on hosts

Options:
    --g5k              Deploying on g5k [default: false]

Deploy enos
    """
    hosts_file = 'current/hosts'
    if not (os.path.exists(hosts_file) and
    os.path.isfile(hosts_file) and
    os.stat(hosts_file).st_size == 0):
        hosts = [host.strip() for host in open("current/hosts", 'r')]
        logging.info("Running ansible")
        exec_dir = os.path.dirname(os.path.realpath(__file__))
        extra_vars = { 'exec_dir': exec_dir,
                       'nodes': hosts,
                       'g5k': g5k}
        launch_playbook = os.path.join(ANSIBLE_PATH, 'enos.yml')
        run_ansible([launch_playbook], 'current/hosts',
                    extra_vars=extra_vars)
    else:
        logging.error("No host to run onto.")


@doc()
def cleanup(**kwargs):
    """
Usage: eov cleanup

Remove everything in the current directory
    """
    shutil.rmtree('current')
    os.makedirs('current')


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
