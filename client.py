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


@doc()
def openvpn(master, name, g5k=False, **kwargs):

    """
Usage: client openvpn MASTER [options]

Connect to the openvpn network. <master> is the ip of the master node

Options:
    -n, --name NAME     Name of the experiment [default: new_node]
    --g5k               Add if the node is on g5k [default: False]
    """
    try:
        url = "http://%s/addnode/%s/%s" % (master, g5k, name)
        result = requests.get(url)
        files = '%s.tar.gz' % name
        open(files, 'wb').write(result.content)
        tar = tarfile.open(files)
        tar.extractall()
        tar.close()
    except:
        logging.info("Encountered an error while getting file")


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
