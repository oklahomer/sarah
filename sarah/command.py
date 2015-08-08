# -*- coding: utf-8 -*-
from typing import Union
from sarah.types import CommandFunction, CommandConfig
from sarah.user_context import UserContext


class Command(object):
    def __init__(self,
                 name: str,
                 function: CommandFunction,
                 module_name: str,
                 config: CommandConfig=None) -> None:
        if not config:
            config = {}
        self.__name = name
        self.__function = function
        self.__module_name = module_name
        self.__config = config

    @property
    def name(self):
        return self.__name

    @property
    def function(self):
        return self.__function

    @property
    def module_name(self):
        return self.__module_name

    @property
    def config(self):
        return self.__config

    def execute(self, *args) -> Union[UserContext, str]:
        args = list(args)
        args.append(self.config)
        return self.function(*args)

    def set_config(self, config: CommandConfig) -> None:
        self.__config = config


class CommandMessage:
    def __init__(self, original_text: str, text: str, sender: str):
        self.__original_text = original_text
        self.__text = text
        self.__sender = sender

    @property
    def original_text(self):
        return self.__original_text

    @property
    def text(self):
        return self.__text

    @property
    def sender(self):
        return self.__sender
