# -*- coding: utf-8 -*-
import random
import re

import pytest
from assertpy import assert_that
from typing import Union, AnyStr, Pattern, Callable, Optional, Any, Dict

from sarah import ValueObject


class TestInit(object):
    # A *bit* complex to be considered as "value object"
    class MyValue(ValueObject):
        def __init__(self,
                     key1: str="spam",
                     key2: str="ham",
                     key3: Dict[str, Any]=None) -> None:
            pass

    class SomeObject(object):
        def do_something(self):
            return random.randrange(0, 100)

    some_object = SomeObject()
    obj1 = MyValue(key1="Foo",
                   key2="ham",
                   key3={'123': "spam", 'ham': 456})

    assert_that(obj1["key1"]).is_equal_to("Foo")
    assert_that(obj1["key2"]).is_equal_to("ham")
    assert_that(obj1["key3"]).is_equal_to({'ham': 456, '123': "spam"})

    obj2 = MyValue(key1="Foo",
                   key3={'ham': 456, '123': "spam"})

    assert_that(obj1).is_equal_to(obj2)
    assert_that(hash(obj1)).is_equal_to(hash(obj2))


class TestOverride(object):
    class MyValueWithInit(ValueObject):
        def __init__(self,
                     pattern: Union[Pattern[str], AnyStr],
                     key1="spam") -> None:
            if isinstance(pattern, str):
                self['pattern'] = re.compile(pattern)

    obj1 = MyValueWithInit(pattern="str",
                           key1="Foo")
    obj2 = MyValueWithInit(pattern=re.compile("str"),
                           key1="Foo")

    assert_that(obj1) \
        .described_as("obj1.pattern is properly converted to regexp pattern") \
        .is_equal_to(obj2)

    assert_that(hash(obj1)).is_equal_to(hash(obj2))


class TestMalformedClassDeclaration(object):
    class MyValueWithKWArgs(ValueObject):
        def __init__(self, **kwargs):
            pass

    with pytest.raises(ValueError) as e:
        obj1 = MyValueWithKWArgs(pattern="str",
                                 key1="Foo")

    assert_that(e.value.args[0]) \
        .is_equal_to("__init__ with *args or **kwargs are not allowed")


class TestCallbackMethodAsValue(object):
    class MyValueWithMethod(ValueObject):
        def __init__(self,
                     callback: Callable[..., Optional[Any]],
                     config: Dict[str, Optional[Any]]) -> None:
            pass

    class SomeObject(object):
        def __init__(self) -> None:
            pass

        def some_method(self) -> str:
            return "dummy string"

    so1 = SomeObject()
    obj1 = MyValueWithMethod(
        so1.some_method,
        {'key': "abc", 'foo': "zzz", 'abc': "foo bar buzz"})
    obj2 = MyValueWithMethod(
        so1.some_method,
        {'abc': "foo bar buzz", 'foo': "zzz", 'key': "abc"})

    assert_that(obj1).is_equal_to(obj2)

    so2 = SomeObject()
    obj3 = MyValueWithMethod(
        so2.some_method,
        {'abc': "foo bar buzz", 'foo': "zzz", 'key': "abc"})

    assert_that(obj1).is_not_equal_to(obj3)


class TestInvalidInplimentation(object):
    class MyInvalidClass(ValueObject):
        pass

    with pytest.raises(NotImplementedError) as e:
        MyInvalidClass()

        assert_that(e).is_instance_of(NotImplementedError)
