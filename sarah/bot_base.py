# -*- coding: utf-8 -*-
import abc
from collections import OrderedDict
import imp
import importlib
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import sys
from typing import Callable, List, Tuple, Union, Optional


class Command(object):
    def __init__(self,
                 name: str,
                 function: Callable,
                 module_name: str,
                 config: Optional[dict]=None) -> None:
        if not config:
            config = {}
        self.name = name
        self.function = function
        self.module_name = module_name
        self.config = config

    def execute(self, *args) -> str:
        args = list(args)
        args.append(self.config)
        return self.function(*args)

    def set_config(self, config: dict) -> None:
        self.config = config


class BotBase(object, metaclass=abc.ABCMeta):
    __commands = {}
    __schedules = {}

    def __init__(self, plugins: Union[List, Tuple]) -> None:
        self.plugins = plugins

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = OrderedDict()
        self.__schedules[self.__class__.__name__] = OrderedDict()

        self.scheduler = BackgroundScheduler()
        self.load_plugins(self.plugins)
        self.add_schedule_jobs(self.schedules)

    @abc.abstractmethod
    def run(self) -> None:
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        pass

    @abc.abstractmethod
    def add_schedule_job(self, command: Command) -> None:
        pass

    def load_plugins(self, plugins: Union[List, Tuple]) -> None:
        for module_config in plugins:
            self.load_plugin(module_config[0])

    def load_plugin(self, module_name: str) -> None:
        try:
            if module_name in sys.modules.keys():
                imp.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except Exception as e:
            logging.warning('Failed to load %s. %s. Skipping.' % (module_name,
                                                                  e))
        else:
            logging.info('Loaded plugin. %s' % module_name)

    def find_command(self, text: str) -> Optional[Command]:
        # Find the first registered command that matches the input text
        command_name = next(
            (k for k in self.commands.keys() if text.startswith(k)), None)

        if command_name is None:
            return None

        # Since command function is class method, when it is called with
        # @command annotation from outside, self.plugins or other object
        # properties are not accessible. So add plugin configuration at here.
        # TODO look for better implementation.
        command = self.commands[command_name]
        plugin_info = next(
            (i for i in self.plugins if i[0] == command.module_name), ())
        if len(plugin_info) > 1:
            command.set_config(plugin_info[1])

        return command

    @property
    def schedules(self) -> OrderedDict:
        return self.__schedules.get(self.__class__.__name__, OrderedDict())

    @classmethod
    def schedule(cls, name: str) -> Callable:
        if cls.__name__ not in cls.__schedules:
            cls.__schedules[cls.__name__] = OrderedDict()

        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            # If command name duplicates, update with the later one.
            # The order stays.
            cls.__schedules[cls.__name__].update(
                {name: Command(name, wrapped_function, func.__module__)})

        return wrapper

    def add_schedule_jobs(self, commands: OrderedDict) -> None:
        for command in list(commands.values()):
            plugin_info = next(
                (i for i in self.plugins if i[0] == command.module_name), ())

            if len(plugin_info) < 2:
                logging.warning(
                    'Missing configuration for schedule job. %s. '
                    'Skipping.' % command.module_name)
                continue

            command.set_config(plugin_info[1])
            self.add_schedule_job(command)

    @property
    def commands(self) -> OrderedDict:
        return self.__commands.get(self.__class__.__name__, OrderedDict())

    @classmethod
    def command(cls, name) -> Callable:
        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            cls.add_command(name, wrapped_function, func.__module__)
            return wrapped_function

        return wrapper

    @classmethod
    def add_command(cls, name: str, func: Callable, module_name: str) -> None:
        if cls.__name__ not in cls.__commands:
            cls.__commands[cls.__name__] = OrderedDict()

        # If command name duplicates, update with the later one.
        # The order stays.
        cls.__commands[cls.__name__].update(
            {name: Command(name, func, module_name)})
