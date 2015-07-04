# -*- coding: utf-8 -*-
import abc
import imp
import importlib
import logging
from apscheduler.schedulers.background import BackgroundScheduler
import sys


class BotBase(object, metaclass=abc.ABCMeta):
    __commands = {}
    __schedules = {}

    def __init__(self, config):
        self.config = config

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = []
        self.__schedules[self.__class__.__name__] = []

        self.scheduler = BackgroundScheduler()
        self.load_plugins(self.config.get('plugins', []))
        self.add_schedule_jobs(self.schedules)

    @abc.abstractmethod
    def run(self):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def add_schedule_job(self):
        pass

    def load_plugins(self, plugins):
        for module_config in plugins:
            self.load_plugin(module_config[0])

    def load_plugin(self, module_name):
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

    def find_command(self, text):
        # Find the first registered command that matches the input text
        command = next((c for c in self.commands if text.startswith(c[0])),
                       None)
        if command is None:
            return None

        config = self.config.get('plugins', ())
        plugin_info = next((i for i in config if i[0] == command[2]), ())

        return {'name': command[0],
                'function': command[1],
                'module_name': command[2],
                'config': plugin_info[1] if len(plugin_info) > 1 else {}}

    @property
    def schedules(self):
        return self.__schedules.get(self.__class__.__name__, [])

    @classmethod
    def schedule(cls, name):
        if cls.__name__ not in cls.__schedules:
            cls.__schedules[cls.__name__] = []

        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            if name in [schedule_set[0] for schedule_set in
                        cls.__schedules[cls.__name__]]:
                logging.info("Skip duplicate schedule. "
                             "module: %s. command: %s." %
                             (func.__module__, name))
            else:
                cls.__schedules[cls.__name__].append((name,
                                                      wrapped_function,
                                                      func.__module__))

        return wrapper

    def add_schedule_jobs(self, jobs):
        for job in jobs:
            plugin_info = next(
                (i for i in self.config.get('plugins', ()) if i[0] == job[2]),
                ())

            if len(plugin_info) < 2:
                logging.warning(
                    'Missing configuration for schedule job. %s. '
                    'Skipping.' % job[2])
                continue

            plugin_config = plugin_info[1]
            self.add_schedule_job(job[0], job[1], job[2], plugin_config)

    @property
    def commands(self):
        return self.__commands.get(self.__class__.__name__, [])

    @classmethod
    def command(cls, name):
        def wrapper(func):
            def wrapped_function(*args, **kwargs):
                return func(*args, **kwargs)

            registered_commands = cls.__commands.get(cls.__name__, [])
            if name in [command_set[0] for command_set in registered_commands]:
                logging.info("Skip duplicate command. "
                             "module: %s. command: %s." %
                             (func.__module__, name))
            else:
                cls.add_command(name, wrapped_function, func.__module__)
                return wrapped_function

        return wrapper

    @classmethod
    def add_command(cls, name, func, module_name):
        if cls.__name__ not in cls.__commands:
            cls.__commands[cls.__name__] = []
        cls.__commands[cls.__name__].append((name, func, module_name))
