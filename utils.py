import os

from docopt import docopt
from copy import deepcopy
from functools import wraps


# Defining global variables
EOV_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
ANSIBLE_PATH = os.path.join(EOV_PATH, 'ansible')
SYMLINK_NAME = os.path.abspath(os.path.join(os.getcwd(), 'current'))

DOC_GLOBAL = {}


def doc(doc_param=None):
    def decorator(fn):
        @wraps(fn)
        def decorated(*args, **kwargs):
            # Format the arguments for convenient use
            new_kwargs = deepcopy(kwargs)
            for k, v in kwargs.items():
                k = k.lower()
                new_kwargs[k.lstrip('-').replace('-', '_')] = v
            # Proceeds with the function execution
            fn(*args, **new_kwargs)
        DOC_GLOBAL[fn.__name__] = decorated
        # https://stackoverflow.com/questions/10307696/how-to-put-a-variable-into-python-docstring
        if doc_param:
            decorated.__doc__ = decorated.__doc__.format(doc_param)
        return decorated
    return decorator


def doc_lookup(fn_name, argv):
    fn = DOC_GLOBAL.get(fn_name, error_lookup)
    return fn(**docopt(fn.__doc__, argv=argv))


def error_lookup(**kwargs):
    exit("%r is not a command. \n%s" % (kwargs['<command>'],
                                        error_lookup.__doc__))
