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

See 'eov <command> --help' for more information
on a specific command.

"""

import os
import shutil
import logging
import yaml
import copy

from docopt import docopt
from flask import Flask, send_from_directory
import execo
import execo_g5k as ex5
from enoslib.api import run_ansible
import jinja2

from utils import (EOV_PATH, ANSIBLE_PATH, CURRENT_PATH, doc,
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
    if 'job' not in locals():
        logging.info("Making a submission")
        job_specs = [(ex5.OarSubmission(resources="nodes="+nodes,
                                        walltime=walltime,
                                        reservation_date=reservation,
                                        job_type="deploy",
                                        name=xp_name), cluster)]
        logging.info("Getting job %s on %s nodes of %s cluster"
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
    hosts_file = '%s/hosts' % CURRENT_PATH
    if not((_check_file_exists(hosts_file) and
            os.stat(hosts_file).st_size != 0)):
        logging.info("Deploying debian on nodes %s" % nodes)
        deployment = ex5.kadeploy.Deployment(hosts=nodes,
                                             env_name='debian9-x64-nfs')
        deployed, undeployed = ex5.kadeploy.deploy(deployment)
        logging.info("Deployed debian on: %s" % ', '.join(map(str, deployed)))
        if undeployed:
            logging.warning("Deployment did not work on: %s" % ', '.
                            join(map(str, deployed)))
        with open(hosts_file, 'w') as f:
            for host in deployed:
                f.write("%s\n" % host)
    else:
        deployed = _get_hosts(hosts_file)
    private_key_path = '%s/ansible' % CURRENT_PATH
    if not _check_file_exists(private_key_path):
        os.system('ssh-keygen -t rsa -N "" -b 4096 -f %s' % private_key_path)
    public_key_path = '%s.pub' % private_key_path
    con_param = {'user': 'root'}
    cmd = execo.action.Put(deployed,
                           [public_key_path],
                           '/root/.ssh/ansible.pub',
                           con_param)
    cmd.run()
    cmd_to_run = "cat /root/.ssh/ansible.pub >> .ssh/authorized_keys"
    cmd = execo.action.Remote(cmd_to_run, deployed, con_param)
    cmd.run()


@doc()
def openvpn(add=None, **kwargs):
    """
Usage: eov openvpn [options]

Deploy openvpn on resources from current/hosts

Options:
    --add NODE         Add defined node
    """
    _create_ansible_conf()
    extra_vars = {'action_type': None}
    if add:
        hosts_file = _add_node_to_hosts(add)
        extra_vars.update({'action_type': 'add'})
    else:
        hosts_file = "%s/hosts" % CURRENT_PATH
    hosts = _get_hosts(hosts_file)
    node_conf, _ = _make_node_configuration(hosts)
    logging.info("Running ansible openvpn with the config:\n%s" % node_conf)
    exec_dir = os.path.dirname(os.path.realpath(__file__))
    extra_vars.update({'exec_dir': exec_dir,
                       'nodes': hosts,
                       'node': add,
                       'config': node_conf})
    launch_playbook = os.path.join(ANSIBLE_PATH, 'openvpn.yml')
    run_ansible([launch_playbook], '%s/hosts' % CURRENT_PATH,
                extra_vars=extra_vars)


# pip target is bugged, so for now, enos dir will be in /tmp/src
# https://github.com/pypa/pip/issues/4390
@doc(EOV_PATH)
def kolla(g5k, conf, action=None, node=None, **kwargs):
    """
Usage: eov kolla [options]

Deploy OpenStack on hosts, using Kolla

Options:
    --g5k               Deploying on g5k [default: false]
    --node NODE         The node to act on
    -a, --action ACTION Define the action to do
    -c, --conf CONF     Which configuration file to use [default: {}/configuration.yml]

    """
    _create_ansible_conf()
    extra_vars = {'g5k': g5k,
                  'node': None,
                  'alias': None,
                  'current_dir': CURRENT_PATH}
    if action and node:
        hosts_file = '%s/%s/hosts' % (CURRENT_PATH, node)
        if _check_file_exists(hosts_file):
            node_conf = _multinode_file(hosts_file, node)
        else:
            raise OsError("No host file")
        if action not in ['add', 'remove', 'rejoin']:
            raise ValueError("The action must be 'add', 'remove' or 'rejoin'")
        if action == 'add':
            _add_node_to_hosts(node)
        alias, address = _add_node_in_reservation(node)
        _add_node_in_multinode(alias, address)
        extra_vars.update({'node': node,
                           'alias': alias})
    elif action:
        raise ValueError("No node to run %s onto" % action)
    else:
        hosts_file = '%s/hosts' % CURRENT_PATH
        node_conf = _multinode_file(hosts_file)
    hosts = _get_hosts(hosts_file)
    logging.info("Running ansible")

    extra_vars.update({'exec_dir': EOV_PATH,
                       'nodes': hosts,
                       'action_type': action if not action else str(action),
                       'config': node_conf})
    extra_vars.update(_kolla_config(conf))
    launch_playbook = os.path.join(ANSIBLE_PATH, 'enos.yml')
    run_ansible([launch_playbook], '%s/hosts' % CURRENT_PATH,
                extra_vars=extra_vars)


def _multinode_file(hosts_file, add=None, **kwargs):
    """
Make configuration and multinode file
    """
    hosts = _get_hosts(hosts_file)
    if add:
        return None
    node_conf, global_conf = _make_node_configuration(hosts)
    private_key_path = _get_private_key(global_conf)
    multinode = _multinode(node_conf, private_key_path)
    with open('%s/multinode' % CURRENT_PATH, 'w') as multinode_file, \
         open ('multinode.part', 'r') as multinode_part:
        multinode_file.write(multinode)
        for line in multinode_part:
            multinode_file.write(line)
    return node_conf


def _check_file_exists(fil):
    return os.path.exists(fil) and os.path.isfile(fil)


def _get_hosts(hosts_file):
    if _check_file_exists(hosts_file):
        hosts = [host.strip() for host in open(hosts_file, 'r')]
    else:
        hosts = None
    return hosts


def _create_ansible_conf():
    if not _check_file_exists('%s/ansible.cfg' % EOV_PATH):
        global_conf = _read_configuration()
        private_key_path = _get_private_key(global_conf)
        variables = {'private_key': private_key_path}
        jinja_conf = "ansible.cfg.j2"
        env = jinja2.Environment(loader=jinja2.PackageLoader('eov'))
        template = env.get_template(jinja_conf)
        render = (template.render(variables))
        with open('%s/ansible.cfg' % EOV_PATH, "w") as f:
            f.write(render)
    else:
        logging.info("Using already existing ansible.cfg")


def _get_private_key(global_conf):
    private_key_path = os.path.expanduser(global_conf['ssh_key'])
    if not _check_file_exists(private_key_path):
        logging.info("%s does not exist, using ~/.ssh/id_rsa instead" %
                     private_key_path)
        private_key_path = '%s/.ssh/id_rsa' % os.path.expanduser("~")
    return private_key_path


def _read_configuration(config_path='%s/configuration.yml' % EOV_PATH):
    if (_check_file_exists(config_path)):
        with open(config_path, "r") as f:
            configuration = yaml.load(f)
        return configuration
    else:
        raise OSError("No configuration file at %s." % config_path)


def _kolla_config(conf):
    global_conf = _read_configuration(conf)
    kolla_dict = global_conf['kolla']
    kolla_conf = {'network_interface': kolla_dict['network_interface'],
                  'neutron_external_interface': kolla_dict['neutron_external_interface'],
                  'kolla_internal_ip': kolla_dict['kolla_internal_ip'],
                  'os_version': kolla_dict['os_version'],
                  'os_password': kolla_dict['os_password'],
                  'images': global_conf['images']}
    return kolla_conf


def _make_node_configuration(hosts):
    variables = {'hosts': hosts}
    global_conf = _read_configuration()
    control_number = range(global_conf['nodes']['control'])
    network_number = range(global_conf['nodes']['network'])
    compute_number = range(global_conf['nodes']['compute'])
    network1 = global_conf['network']['network1']
    network2 = global_conf['network']['network2']
    mask = global_conf['network']['mask']
    if 'all-in-one' in global_conf:
        node_index = _all_in_one(global_conf,
                                 control_number,
                                 network_number,
                                 compute_number)
    variables.update({'node_index': node_index,
                      'controls': control_number,
                      'networks': network_number,
                      'computes': compute_number,
                      'network1': network1,
                      'network2': network2,
                      'mask': mask})
    jinja_conf = "post_conf.yaml.j2"
    env = jinja2.Environment(
        loader=jinja2.PackageLoader('eov')
    )
    template = env.get_template(jinja_conf)
    render = (template.render(variables))
    node_conf = yaml.load(render)
    return node_conf, global_conf


def _all_in_one(global_conf, control_number, network_number, compute_number):
    node_number = {'control': [], 'network': [], 'compute': []}
    n_cont = global_conf['all-in-one']['control']
    n_net = global_conf['all-in-one']['network']
    n_comp = global_conf['all-in-one']['compute']
    for cont in control_number:
        node_number['control'].append(n_cont + cont)
    for net in network_number:
        node_number['network'].append(n_net + net)
    for comp in compute_number:
        node_number['compute'].append(n_comp + comp)
    return node_number


def _multinode(node_conf, private_key_path):
    conf_copy = copy.deepcopy(node_conf)
    for typ in conf_copy['resources']:
        for node in conf_copy['resources'][typ]:
            ssh = ('ssh' if node['host'] != 'localhost' else 'local')
            node.update({'parameters':
                         ("ansible_ssh_user=root "
                          "ansible_connection={} "
                          "ansible_ssh_private_key={} "
                          "ansible_ssh_common_args="
                          "'-o StrictHostKeyChecking=no "
                          "-o UserKnownHostsFile=/dev/null' "
                          "neutron_external_interface=tap1 "
                          "network_interface=tap0 ").format(ssh,
                                                            private_key_path)})
    variables = {'control': conf_copy['resources']['control'],
                 'network': conf_copy['resources']['network'],
                 'compute': conf_copy['resources']['compute']}
    env = jinja2.Environment(
        loader=jinja2.PackageLoader('eov')
    )
    template = env.get_template('multinode_top.j2')
    multinode_conf = (template.render(variables))
    return multinode_conf


def _add_node_to_hosts(add):
    hosts_file = '%s/hosts' % CURRENT_PATH
    node_directory = '%s/%s' % (CURRENT_PATH, add)
    hosts_for_node = '%s/hosts' % node_directory
    if (_check_file_exists(hosts_file) and
        os.stat(hosts_file).st_size != 0):
        if not os.path.exists(node_directory):
                os.makedirs(node_directory)
        if not _check_file_exists(hosts_for_node):
            shutil.copy2(hosts_file,
                         hosts_for_node)
        logging.info("You have requested to add %s" % add)
        with open(hosts_for_node, "r+") as f:
            for line in f:
                if add in line:
                    break
            else:
                logging.info("Adding %s to host file" % add)
                f.write('\n%s' % add)
    else:
        raise OSError("No host file or the host file is empty.")
    return hosts_for_node


def _add_node_in_reservation(add):
    current_nodes = '%s/reservation.yaml' % CURRENT_PATH
    if not _check_file_exists(current_nodes):
        shutil.copy2('reservation.yaml',
                     current_nodes)
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
    # its number is the number of node plus one
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
    multinode_file = '%s/multinode' % CURRENT_PATH
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
        for line in multinode_final:
            f.write("%s" % line)


@doc()
def cleanup(**kwargs):
    """
Usage: eov cleanup

Remove temporary files in the 'current' directory
    """
    for root, dirs, files in os.walk(CURRENT_PATH):
        for fil in files:
            if fil != ".gitignore":
                os.remove(os.path.join(root, fil))
    ansible_cfg = '%s/ansible.cfg' % EOV_PATH
    if _check_file_exists(ansible_cfg):
        os.remove(ansible_cfg)
    logging.info("Cleaned up current directory")


@app.route('/')
def ssh_public_key():
    global_conf = _read_configuration()
    public_key_path = _get_private_key(global_conf)
    with open(public_key_path) as f:
        lines = f.readlines()
    return lines[0]


@app.route('/openvpn/<add>')
def openvpn_add(add):
    openvpn(add)
    return "You have been added to openvpn.\n"


@app.route('/enos/<action>/<g5k>/<name>')
def enos_action(action, g5k, name):
    if g5k.lower() == "true" or g5k.lower() == "g5k":
        g5k = True
    else:
        g5k = False
    kolla(g5k=g5k, action=action, node=name)
    return "Action %s has been executed for %s\n" % (action, name)


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
