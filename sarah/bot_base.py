# -*- coding: utf-8 -*-
import abc
import imp
import importlib
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import sys
from typing import Callable, List, Tuple, Union, Dict, Optional


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

    def execute(self, msg: Dict) -> str:
        return self.function(msg, self.config)

    def set_config(self, config: dict) -> None:
        self.config = config


class BotBase(object, metaclass=abc.ABCMeta):
    __commands = {}
    __schedules = {}

    def __init__(self, plugins: Union[List, Tuple]) -> None:
        self.plugins = plugins

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = []
        self.__schedules[self.__class__.__name__] = []

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
    def add_schedule_job(self, name: str,
                         func: Callable,
                         module_name: str,
                         plugin_config: dict) -> None:
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
        command = next(
            (c for c in self.commands if text.startswith(c.name)),
            None)

        if command is None:
            return None

        # Since command function is class method, when it is called with
        # @command annotation from outside, self.plugins or other object
        # properties are not accessible. So add plugin configuration at here.
        # TODO look for better implementation.
        plugin_info = next(
            (i for i in self.plugins if i[0] == command.module_name), ())
        if len(plugin_info) > 1:
            command.set_config(plugin_info[1])

        return command

    @property
    def schedules(self) -> List[Command]:
        return self.__schedules.get(self.__class__.__name__, [])

    @classmethod
    def schedule(cls, name: str) -> Callable:
        if cls.__name__ not in cls.__schedules:
            cls.__schedules[cls.__name__] = []

        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            if name in [command.name for command in
                        cls.__schedules[cls.__name__]]:
                logging.info("Skip duplicate schedule. "
                             "module: %s. command: %s." %
                             (func.__module__, name))
            else:
                cls.__schedules[cls.__name__].append(
                    Command(name, wrapped_function, func.__module__))

        return wrapper

    def add_schedule_jobs(self, jobs: List[Command]) -> None:
        for job in jobs:
            plugin_info = next(
                (i for i in self.plugins if i[0] == job.module_name),
                ())

            if len(plugin_info) < 2:
                logging.warning(
                    'Missing configuration for schedule job. %s. '
                    'Skipping.' % job.module_name)
                continue

            job.set_config(plugin_info[1])
            self.add_schedule_job(job)

    @property
    def commands(self) -> List:
        return self.__commands.get(self.__class__.__name__, [])

    @classmethod
    def command(cls, name) -> Callable:
        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            registered_commands = cls.__commands.get(cls.__name__, [])
            if name in [command.name for command in registered_commands]:
                logging.info("Skip duplicate command. "
                             "module: %s. command: %s." %
                             (func.__module__, name))
            else:
                cls.add_command(name, wrapped_function, func.__module__)
                return wrapped_function

        return wrapper

    @classmethod
    def add_command(cls, name: str, func: Callable, module_name: str) -> None:
        if cls.__name__ not in cls.__commands:
            cls.__commands[cls.__name__] = []
        cls.__commands[cls.__name__].append(Command(name, func, module_name))
