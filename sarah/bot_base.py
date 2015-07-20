# -*- coding: utf-8 -*-
import abc
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps
import imp
import importlib
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import sys
from typing import Callable, Optional, Sequence
from sarah.thread import ThreadExecutor
from sarah.types import CommandFunction, PluginConfig, AnyFunction, \
    CommandConfig


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

    def execute(self, *args) -> str:
        args = list(args)
        args.append(self.__config)
        return self.__function(*args)

    def set_config(self, config: CommandConfig) -> None:
        self.__config = config


class BotBase(object, metaclass=abc.ABCMeta):
    __commands = {}
    __schedules = {}

    def __init__(self,
                 plugins: Sequence[PluginConfig]=None,
                 max_workers: Optional[int]=None) -> None:
        self.plugins = plugins
        self.max_workers = max_workers
        self.scheduler = BackgroundScheduler()

        # To be set on run()
        self.worker = None
        self.message_worker = None

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = OrderedDict()
        self.__schedules[self.__class__.__name__] = OrderedDict()

    @abc.abstractmethod
    def add_schedule_job(self, command: Command) -> None:
        pass

    @abc.abstractmethod
    def connect(self) -> None:
        pass

    def run(self) -> None:
        # Setup required workers
        self.worker = ThreadPoolExecutor(max_workers=self.max_workers) \
            if self.max_workers else None
        self.message_worker = ThreadExecutor()

        # Load plugins
        if self.plugins:
            self.load_plugins(self.plugins)

        # Set scheduled job
        self.add_schedule_jobs(self.schedules)
        self.scheduler.start()

        self.connect()

    def stop(self) -> None:
        logging.info('STOP MESSAGE WORKER')
        self.message_worker.shutdown(wait=False)

        logging.info('STOP CONCURRENT WORKER')
        if self.worker:
            self.worker.shutdown(wait=False)

        logging.info('STOP SCHEDULER')
        if self.scheduler.running:
            try:
                self.scheduler.shutdown()
                logging.info('CANCELLED SCHEDULED WORK')
            except Exception as e:
                logging.error(e)

    @classmethod
    def concurrent(cls, callback_function: AnyFunction):
        @wraps(callback_function)
        def wrapper(self, *args, **kwargs):
            if self.worker:
                return self.worker.submit(callback_function,
                                          self,
                                          *args,
                                          **kwargs)
            else:
                return callback_function(self, *args, **kwargs)

        return wrapper

    def enqueue_sending_message(self, function, *args, **kwargs) -> Future:
        return self.message_worker.submit(function, *args, **kwargs)

    def load_plugins(self, plugins: Sequence[PluginConfig]) -> None:
        for module_config in plugins:
            self.load_plugin(module_config[0])

    @staticmethod
    def load_plugin(module_name: str) -> None:
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
    def schedule(cls, name: str) -> Callable[[CommandFunction], None]:
        if cls.__name__ not in cls.__schedules:
            cls.__schedules[cls.__name__] = OrderedDict()

        def wrapper(func: CommandFunction) -> None:
            @wraps(func)
            def wrapped_function(*args, **kwargs) -> str:
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
    def command(cls, name: str) -> Callable[[CommandFunction],
                                            CommandFunction]:
        def wrapper(func: CommandFunction) -> CommandFunction:
            @wraps(func)
            def wrapped_function(*args, **kwargs) -> str:
                return func(*args, **kwargs)

            cls.add_command(name, wrapped_function, func.__module__)
            return wrapped_function

        return wrapper

    @classmethod
    def add_command(cls, name: str,
                    func: CommandFunction,
                    module_name: str) -> None:
        if cls.__name__ not in cls.__commands:
            cls.__commands[cls.__name__] = OrderedDict()

        # If command name duplicates, update with the later one.
        # The order stays.
        cls.__commands[cls.__name__].update(
            {name: Command(name, func, module_name)})


class SarahException(Exception):
    pass


concurrent = BotBase.concurrent
