# -*- coding: utf-8 -*-
import hashlib
from inspect import getfullargspec  # type: ignore

from typing import Any, Dict


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
        self.__stash[key] = value

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.__stash)

    def __hash__(self) -> int:
        return hash(Util.dict_to_hex(self.__stash))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return hash(self) == hash(other)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def keys(self):
        return self.__stash.keys()


class Util(object):
    @classmethod
    def dict_to_hex(cls, d: Dict[str, Any]) -> str:
        md5 = hashlib.md5()
        keys = sorted(d.keys())
        for key in keys:
            value = d[key]
            if isinstance(value, dict):
                value = cls.dict_to_hex(value)
            else:
                value = hash('%s::%s' % (type(value), value))
            value = "%s::%s" % (key, value)
            md5.update(value.encode('utf-8'))
        return md5.hexdigest()
