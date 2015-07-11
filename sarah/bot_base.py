# -*- coding: utf-8 -*-
import abc
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
import imp
import importlib
import logging
from queue import Queue, Empty
import threading
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

    def __init__(self,
                 plugins: Union[List, Tuple],
                 max_workers: Optional[int]=None) -> None:
        self.plugins = plugins
        self.worker = ThreadPoolExecutor(max_workers=max_workers) \
            if max_workers else None

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = OrderedDict()
        self.__schedules[self.__class__.__name__] = OrderedDict()

        self.stop_event = threading.Event()
        self.sending_queue = None
        self.scheduler = BackgroundScheduler()
        self.load_plugins(self.plugins)
        self.add_schedule_jobs(self.schedules)

    @abc.abstractmethod
    def run(self) -> None:
        pass

    @abc.abstractmethod
    def add_schedule_job(self, command: Command) -> None:
        pass

    def stop(self) -> None:
        self.stop_event.set()
        if self.worker:
            self.worker.shutdown(wait=False)

    @classmethod
    def concurrent(cls, callback_function):
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

    def supervise_enqueued_message(self) -> None:
        """ Supervise the message queue, and send queued messages to chat room

        Send messages queued via concurrent_sending_message(). One message is
        sent at a time, so it is suitable to ensure thread-safety and avoid
        sending multiple message in concurrent jobs.
        """
        self.sending_queue = Queue()

        def _supervise(stop_event: threading.Event) -> None:
            while not stop_event.is_set():
                try:
                    func = self.sending_queue.get()
                except Empty:
                    # Queue is empty.
                    # sending_queue.empty() doesn't guarantee its emptiness,
                    # so just call get() and see if exception is raised.
                    continue
                except Exception as e:
                    logging.error('Error on getting task from queue. %s', e)
                    continue

                try:
                    func()
                except Exception as e:
                    logging.error('Error on sending response. %s', e)
            return

        t = threading.Thread(target=_supervise, args=(self.stop_event,))
        t.setDaemon(True)
        t.start()

    def enqueue_sending_message(self, function, *args, **kwargs):
        if self.sending_queue is None:
            msg = ("To utilize this method, supervise_enqueued_message() must "
                   "be called in run()")
            logging.error(msg)
            raise SarahException(msg)
        else:
            self.sending_queue.put_nowait(lambda: function(*args, **kwargs))

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
            @wraps(func)
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
            @wraps(func)
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


class SarahException(Exception):
    pass


concurrent = BotBase.concurrent
