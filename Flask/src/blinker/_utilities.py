from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()
from builtins import *
from weakref import ref

from blinker._saferef import BoundMethodWeakref
import collections


try:
    callable
except NameError:
    def callable(object):
        return hasattr(object, '__call__')


try:
    from collections import defaultdict
except:
    class defaultdict(dict):

        def __init__(self, default_factory=None, *a, **kw):
            if (default_factory is not None and
                not hasattr(default_factory, '__call__')):
                raise TypeError('first argument must be callable')
            dict.__init__(self, *a, **kw)
            self.default_factory = default_factory

        def __getitem__(self, key):
            try:
                return dict.__getitem__(self, key)
            except KeyError:
                return self.__missing__(key)

        def __missing__(self, key):
            if self.default_factory is None:
                raise KeyError(key)
            self[key] = value = self.default_factory()
            return value

        def __reduce__(self):
            if self.default_factory is None:
                args = tuple()
            else:
                args = self.default_factory,
            return type(self), args, None, None, list(self.items())

        def copy(self):
            return self.__copy__()

        def __copy__(self):
            return type(self)(self.default_factory, self)

        def __deepcopy__(self, memo):
            import copy
            return type(self)(self.default_factory,
                              copy.deepcopy(list(self.items())))

        def __repr__(self):
            return 'defaultdict(%s, %s)' % (self.default_factory,
                                            dict.__repr__(self))


try:
    from contextlib import contextmanager
except ImportError:
    def contextmanager(fn):
        def oops(*args, **kw):
            raise RuntimeError("Python 2.5 or above is required to use "
                               "context managers.")
        oops.__name__ = fn.__name__
        return oops

class _symbol(object):

    def __init__(self, name):
        """Construct a new named symbol."""
        self.__name__ = self.name = name

    def __reduce__(self):
        return symbol, (self.name,)

    def __repr__(self):
        return self.name
_symbol.__name__ = 'symbol'


class symbol(object):
    """A constant symbol.

    >>> symbol('foo') is symbol('foo')
    True
    >>> symbol('foo')
    foo

    A slight refinement of the MAGICCOOKIE=object() pattern.  The primary
    advantage of symbol() is its repr().  They are also singletons.

    Repeated calls of symbol('name') will all return the same instance.

    """
    symbols = {}

    def __new__(cls, name):
        try:
            return cls.symbols[name]
        except KeyError:
            return cls.symbols.setdefault(name, _symbol(name))


def hashable_identity(obj):
    if hasattr(obj, 'im_func'):
        return (id(obj.__func__), id(obj.__self__))
    else:
        return id(obj)


WeakTypes = (ref, BoundMethodWeakref)


class annotatable_weakref(ref):
    """A weakref.ref that supports custom instance attributes."""


def reference(object, callback=None, **annotations):
    """Return an annotated weak ref."""
    if isinstance(object, collections.Callable):
        weak = callable_reference(object, callback)
    else:
        weak = annotatable_weakref(object, callback)
    for key, value in list(annotations.items()):
        setattr(weak, key, value)
    return weak


def callable_reference(object, callback=None):
    """Return an annotated weak ref, supporting bound instance methods."""
    if hasattr(object, 'im_self') and object.__self__ is not None:
        return BoundMethodWeakref(target=object, on_delete=callback)
    elif hasattr(object, '__self__') and object.__self__ is not None:
        return BoundMethodWeakref(target=object, on_delete=callback)
    return annotatable_weakref(object, callback)