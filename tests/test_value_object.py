# -*- coding: utf-8 -*-
import pytest
from typing import Union, AnyStr, Pattern
from sarah import ValueObject
import re


class TestInit(object):
    class MyValue(ValueObject):
        def __init__(self, key1="spam", key2="ham", key3=None):
            pass

    obj1 = MyValue(key1="Foo",
                   key2="ham",
                   key3={'123': "spam", 'ham': 456})
    obj2 = MyValue(key1="Foo",
                   key3={'ham': 456, '123': "spam"})

    assert obj1['key1'] == "Foo"
    assert obj1['key2'] == "ham"
    assert obj1['key3'] == {'ham': 456, '123': "spam"}

    assert obj1 == obj2
    assert hash(obj1) == hash(obj2)


class TestOverride(object):
    class MyValueWithInit(ValueObject):
        def __init__(self, pattern: Union[Pattern, AnyStr]=None, key1="spam"):
            if isinstance(pattern, str):
                self['pattern'] = re.compile(pattern)

    obj1 = MyValueWithInit(pattern="str",
                           key1="Foo")
    obj2 = MyValueWithInit(pattern=re.compile("str"),
                           key1="Foo")

    assert obj1['key1'] == "Foo"

    assert obj1 == obj2
    assert hash(obj1) == hash(obj2)


class TestMalformedClassDeclaration(object):
    class MyValueWithKWArgs(ValueObject):
        def __init__(self, **kwargs):
            pass

    with pytest.raises(ValueError) as e:
        obj1 = MyValueWithKWArgs(pattern="str",
                                 key1="Foo")

    assert e.value.args[0] == "__init__ with *args or **kwargs are not allowed"
