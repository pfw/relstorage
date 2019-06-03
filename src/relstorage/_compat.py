# -*- coding: utf-8 -*-
"""
Compatibility shims.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# pylint:disable=unused-import,invalid-name,no-member,undefined-variable
# pylint:disable=no-name-in-module

import platform
import sys

# XXX: This is a private module in ZODB, but it has a lot
# of knowledge about how to choose the right implementation
# based on Python version and implementation. We at least
# centralize the import from here.
from ZODB._compat import HIGHEST_PROTOCOL
from ZODB._compat import Pickler
from ZODB._compat import Unpickler
from ZODB._compat import dump
from ZODB._compat import dumps
from ZODB._compat import loads


PY3 = sys.version_info[0] == 3
PY2 = not PY3
PYPY = platform.python_implementation() == 'PyPy'

# Dict support

if PY3:
    def list_values(d):
        return list(d.values())
    iteritems = dict.items
    iterkeys = dict.keys
    itervalues = dict.values
else:
    list_values = dict.values
    iteritems = dict.iteritems
    iterkeys = dict.iterkeys
    itervalues = dict.itervalues

# Types

if PY3:
    string_types = (str,)
    unicode = str
else:
    string_types = (basestring,)
    unicode = unicode

try:
    from abc import ABC
except ImportError:
    import abc
    ABC = abc.ABCMeta('ABC', (object,), {})
    del abc

# Functions
if PY3:
    xrange = range
    intern = sys.intern
    from base64 import encodebytes as base64_encodebytes
    from base64 import decodebytes as base64_decodebytes
    casefold = str.casefold
else:
    xrange = xrange
    intern = intern
    from base64 import encodestring as base64_encodebytes
    from base64 import decodestring as base64_decodebytes
    casefold = str.lower


def get_this_psutil_process():
    # Returns a freshly queried object each time.
    try:
        from psutil import Process, AccessDenied
        # Make sure it works (why would we be denied access to our own process?)
        try:
            proc = Process()
            proc.memory_full_info()
        except AccessDenied: # pragma: no cover
            proc = None
    except ImportError:
        proc = None
    return proc

def get_memory_usage():
    """
    Get a number representing the current memory usage.

    Returns 0 if this is not available.
    """
    proc = get_this_psutil_process()
    if proc is None:
        return 0

    rusage = proc.memory_full_info()
    # uss only documented available on Windows, Linux, and OS X.
    # If not available, fall back to rss as an aproximation.
    mem_usage = getattr(rusage, 'uss', 0) or rusage.rss
    return mem_usage
