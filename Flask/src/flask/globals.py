# -*- coding: utf-8 -*-
"""
    flask.globals
    ~~~~~~~~~~~~~

    Defines all the global objects that are proxies to the current
    active context.

    :copyright: (c) 2011 by Armin Ronacher.
    :license: BSD, see LICENSE for more details.
"""
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import *

from functools import partial
from werkzeug.local import LocalStack, LocalProxy

def _lookup_object(name):
    top = _request_ctx_stack.top
    if top is None:
        raise RuntimeError('working outside of request context')
    return getattr(top, name)


# context locals
_request_ctx_stack = LocalStack()
current_app = LocalProxy(partial(_lookup_object, 'app'))
request = LocalProxy(partial(_lookup_object, 'request'))
session = LocalProxy(partial(_lookup_object, 'session'))
g = LocalProxy(partial(_lookup_object, 'g'))