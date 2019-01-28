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


@doc()
def openvpn(master, name, g5k=False, **kwargs):

    """
Usage: client openvpn MASTER [options]

Connect to the openvpn network. <master> is the ip of the master node

Options:
    -n, --name NAME     Name of the node to add [default: new_node]
    --g5k               Add if the node is on g5k [default: False]
    """
    # Get file content from master node
    try:
        url = "http://%s/addnode/%s/%s" % (master, g5k, name)
        logging.info("Getting the required files")
        result = requests.get(url)
    except:
        logging.error("Encountered an error while getting file")
    # Put the content into a tar
    files = '%s.tar.gz' % name
    open(files, 'wb').write(result.content)
    # Untaring files
    try:
        tar = tarfile.open(files)
        tar.extractall()
        tar.close()
    except:
        logging.error("The files could not be extracted")
    # Put openvpn shared key at the proper place, i.e.
    # /etc/openvpn/openvpn-shared-key.key
    shutil.move("%s/openvpn-shared-key.key" % name,
                "/etc/openvpn/openvpn-shared-key.key")
    # Put delete route file at the proper place, i.e.
    # from ansible/roles/openvpn/files/delete_route.sh to
    # /root/delete_route.sh, mode: "u=rwx,g=r,o=r"
    shutil.copyfile("ansible/roles/openvpn/files/delete_route.sh",
                    "/root/delete_route.sh")
    os.chmod("/root/delete_route.sh", 0o744)
    # Using client.conf
    # cd root/{{ inventory_hostname }}/ ; openvpn --daemon --config client.conf
    os.system("openvpn --daemon --config /root/%s/client.conf" % name)
    # sleep 4
    time.sleep(4)
    # Using client1.conf
    # cd root/{{ inventory_hostname }}/ ; openvpn --daemon --config client1.conf
    os.system("openvpn --daemon --config /root/%s/client1.conf" % name)
    # Using docker0 interface fix file
    shutil.copyfile("ansible/roles/openvpn/templates/create_docker0.sh.j2",
                    "/root/create_docker0.sh")
    os.chmod("/root/create_docker0.sh", 0o744)
    subprocess.call(['/root/create_docker0.sh'])


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
