#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Do client stuff

Usage:
  client [-h|--help] <command> [<args>...]

General options:
  -h --help           Show this help message.

Commands:
  add_ssh             Add master ssh key to authorized keys
  openvpn             Deploy OpenVPN on resources
  enos                Deploy enos
  cleanup             Cleans the current experiment directory

See 'client <command> --help' for more information
on a specific command.

"""

import os
import tarfile
import logging
import requests
import shutil
import time
import subprocess

from docopt import docopt

from utils import (EOV_PATH, ANSIBLE_PATH, SYMLINK_NAME, doc,
doc_lookup)


# Formatting the logger

logger = logging.getLogger('logger')
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%d-%b-%y %H:%M:%S')


@doc()
def add_ssh(master, **kwargs):

    """
Usage: client add_ssh MASTER

Add master ssh key to the node. MASTER is the ip of the master node
    """
    key = requests.get("http://%s/" % master)
    authorized_keys = '%s/.ssh/authorized_keys' % os.path.expanduser("~")
    with open(authorized_keys, "a") as f:
        f.write(key.content)
    logging.info("%s can now ssh on this machine" % master)


@doc()
def openvpn(master, name, **kwargs):

    """
Usage: client openvpn MASTER [options]

Connect to the openvpn network. MASTER is the ip of the master node

Options:
    -n, --name NAME     Name of the node to add [default: new_node]
    """
    # Get file content from master node
    try:
        url = "http://%s/openvpn/%s" % (master, name)
        logging.info("Getting the required files and installing dependencies")
        result = requests.get(url)
        if result.status_code == requests.codes.ok:
            logging.info("You have correctly been added to openvpn")
    except OSError as error:
        logging.error(error)
        logging.error("Encountered an error while joining openvpn")
        raise


@doc()
def enos(master, name, action, g5k=False, **kwargs):

    """
Usage: client enos MASTER [options]

Join the existing Openstack. <master> is the ip of the master node

Options:
    -n, --name NAME      Name of the node to act on [default: new_node]
    --g5k                Specify if the node is on g5k [default: False]
    -a, --action ACTION  Action to run (add, remove or rejoin)
    """
    if action not in ['add', 'remove', 'rejoin']:
        raise ValueError("The action must be 'add', 'remove' or 'rejoin'")
    # Request to be added
    try:
        url = "http://%s/enos/%s/%s/%s" % (master, action, g5k, name)
        logging.info("Executing %s" % action)
        result = requests.get(url)
        if result.status_code == requests.codes.ok:
            logging.info("%s has correctly been executed" % action.capitalize())
    except Exception as error:
        logging.error("Encountered an error while adding the node")
        logging.error(error)
        raise


@doc()
def help(**kwargs):
    """
Usage: eov help

Show the help message
    """
    print(__doc__)


if __name__ == '__main__':
    args = docopt(__doc__,
                  version='Enos OpenVPN client version 1.0.0',
                  options_first=True)

    argv = [args['<command>']] + args['<args>']

    doc_lookup(args['<command>'], argv)
