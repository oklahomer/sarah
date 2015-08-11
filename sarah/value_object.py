# -*- coding: utf-8 -*-
from inspect import getfullargspec
from typing import Any


class ValueObject(object):
    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)

        # "ValueError: Function has keyword-only arguments or annotations, use
        # getfullargspec() API which can support them"
        # names, varargs, keywords, defaults = getargspec(self.__init__)
        names, varargs, keywords, defaults = getfullargspec(self.__init__)[:4]

        # Check __init__'s declaration
        if varargs or keywords:
            raise ValueError("__init__ with *args or **kwargs are not allowed")

        defaults = () if not defaults else defaults
        self.__stash = dict()
        self.__stash.update(dict(zip(names[:0:-1], defaults[::-1])))
        self.__stash.update(dict(zip(names[1:], args)))
        self.__stash.update(kwargs.items())

        # # Dynamically adding properties doesn't help because these properties
        # # are not recognized by IDEs.
        # # Developer should explicitly implement methods with @property
        # # decorator to provide accessors.
        # for key in self.__stash.keys():
        #     if key not in self.__dict__:
        #         setattr(self, key, self.__stash[key])

        return self

    def __init__(self):
        # Values are already set on __new__.
        # Override this method when value modification on initialization is
        # required.
        pass

    def __getitem__(self, key) -> Any:
        return self.__stash[key]

    def __setitem__(self, key, value) -> Any:
        # TODO Currently supporting value assignment, but will be removed.
        self.__stash[key] = value

    def __repr__(self):
        null = object()
        names, _, _, defaults = getfullargspec(self.__init__)[:4]
        names.pop(0)  # Skip the first argument, own class
        values = [self.__stash[arg] for arg in names]
        defaults = () if not defaults else defaults
        defaults = defaults[1:] if len(defaults) == len(
            names) + 1 else defaults
        defaults = (null,) * (len(names) - len(defaults)) + defaults
        return '%s(%s)' % (
            self.__class__.__name__,
            ', '.join(repr(a) for a, d in zip(values, defaults) if a != d))

    def __hash__(self) -> int:
        return hash(repr(self))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return repr(self) == repr(other)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)
