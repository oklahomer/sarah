# -*- coding: utf-8 -*-
from typing import Callable, Pattern, Union, AnyStr
from typing import Sequence
import re


class InputOption(object):
    def __init__(self,
                 pattern: Union[Pattern, AnyStr],
                 next_step: Callable) -> None:
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        self.__pattern = pattern
        self.__next_step = next_step

    @property
    def pattern(self) -> Pattern:
        return self.__pattern

    @property
    def next_step(self) -> Callable:
        return self.__next_step

    def match(self, msg: str) -> bool:
        return self.pattern.match(msg)


class UserContext(object):
    def __init__(self,
                 message: str,
                 help_message: str,
                 input_options: Sequence[InputOption]) -> None:
        self.__message = message
        self.__help_message = help_message
        self.__input_options = input_options

    def __str__(self):
        return self.message

    @property
    def message(self) -> str:
        return self.__message

    @property
    def help_message(self) -> str:
        return self.__help_message

    @property
    def input_options(self) -> Sequence[InputOption]:
        return self.__input_options
