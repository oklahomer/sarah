# -*- coding: utf-8 -*-
"""Provide mechanism to represent "value object" in a broad sense.

In this project, consider value object as simple POJO-like object with
following characteristics:

    - no setter
    - equality calculation based on field values.

This is not recommended, but is allowed to set dictionary as its member for
convenience. The whole point of using this "value object" mechanism in this
project is to reduce the ambiguity of passing ambiguous dictionary all around,
but do not hesitate to use them when using dictionary seems more appropriate.

When dictionary is assigned as its member, equality is properly calculated by
recursive comparison.
"""
import hashlib
import inspect
from inspect import getfullargspec  # type: ignore
from typing import Any, Dict, List


class ValueObject(object):
    """Represent "value object" in a broad sense.

    In this project, consider this as simple POJO-like object with following
    characteristics: a) no setter and b) equality calculation based on field
    values. This class works as base class for those value objects.

    This is not recommended, but is allowed to set dictionary as its member for
    convenience. The whole point of using this "value object" mechanism in this
    project is to reduce the ambiguity of passing ambiguous dictionary all
    around, but do not hesitate to use them when using dictionary seems more
    appropriate.

    When dictionary is assigned as its member, equality is properly calculated
    by recursive comparison.
    """

    def __new__(cls, *args, **kwargs) -> 'ValueObject':
        """Create new instance with given arguments and default values.

        On object initialization, this receives all arguments and assign them
        to new instance. Default value is retrieved via __init__ and is
        assigned if no value is given. Assigned values are stored in an
        internal dictionary. This dictionary is NOT meant to be accessed from
        outside.

        This does not dynamically create accessor because IDEs such as
        PyCharm do not recognize them. Its concrete class should provide
        accessor for users' convenience.
        """
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

    def __init__(self) -> None:
        """Declare arguments and default values as part of its signature.

        When object is initialized, given arguments and values are passed to
        __new__ and are stored internally. The signature below creates Friend
        object with first_name and last_name as its member.

        Friend(ValueObject):
          def __init__(self, first_name: str, last_name: str = "Corleone"):
            pass

        When called as Friend(first_name="Vito"), this instance ends up having
        Vito as first_name and Corleone as last_name. Since last_name is not
        given on initialization, this value is derived from method signature.

        If you wish, you can modify this object's member at this point; setter
        does not allow assignment after initialization. You may normalize some
        values like below:

        Friend(ValueObject):
          def __init__(self, first_name: str, last_name: str = "corleone"):
            self['first_name'] = str.capitalize(first_name)
            self['last_name'] = str.capitalize(last_name)
        """
        # Values are already set on __new__.
        # Override this method when value modification on initialization is
        # required.
        raise NotImplementedError()

    def __getitem__(self, key) -> Any:
        """Provide access to internal stored value in a form of obj[key]."""
        return self.__stash[key]

    def __setitem__(self, key, value) -> None:
        """Setter for stored values.

        This can only be called from __init__ so the object becomes
        semi-immutable after initialization.
        """
        # Allows value modification only in __init__.
        caller_method = inspect.getouterframes(inspect.currentframe(), 2)[1][3]
        if caller_method != "__init__":
            raise AttributeError

        self.__stash[key] = value

    def __repr__(self) -> str:
        return '%s(%s)' % (self.__class__.__name__, self.__stash)

    def __hash__(self) -> int:
        return hash(Util.dict_to_hex(self.__stash))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False

        return hash(self) == hash(other)

    def __ne__(self, other) -> bool:
        return not self.__eq__(other)

    def keys(self) -> List[str]:
        """Return all keys of stored value."""
        return self.__stash.keys()


class Util(object):
    """Provide utility functions for ValueObject."""

    @classmethod
    def dict_to_hex(cls, d: Dict[str, Any]) -> str:
        """Return digested value of dictionary.

        This is to be used for objects' equity comparison.

        :param d: Dictionary.
        """
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
