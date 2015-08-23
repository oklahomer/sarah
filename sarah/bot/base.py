# -*- coding: utf-8 -*-
import abc
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps
import imp
import importlib
import logging
import re
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from typing import Sequence, Optional, Callable, Union
from sarah.bot.types import PluginConfig, AnyFunction, CommandFunction
from sarah.bot.values import Command, CommandMessage, UserContext
from sarah.thread import ThreadExecutor


class Base(object, metaclass=abc.ABCMeta):
    __commands = {}
    __schedules = {}
    __instances = {}

    def __init__(self,
                 plugins: Sequence[PluginConfig]=None,
                 max_workers: Optional[int]=None) -> None:
        if not plugins:
            plugins = ()
        self.plugin_modules = [p[0] for p in plugins]

        # {module_name: config, ...}
        self.plugin_config = {}
        for plugin in plugins:
            if len(plugin) > 1:
                self.plugin_config[plugin[0]] = plugin[1]

        self.max_workers = max_workers
        self.scheduler = BackgroundScheduler()
        self.user_context_map = {}

        # To be set on run()
        self.worker = None
        self.message_worker = None

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = []
        self.__schedules[self.__class__.__name__] = []

        # To refer to this instance from class method decorator
        self.__instances[self.__class__.__name__] = self

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
        if self.plugin_modules:
            self.load_plugins(self.plugin_modules)

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

    def load_plugins(self, plugin_modules: Sequence[str]) -> None:
        for module in plugin_modules:
            self.load_plugin(module)

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

    def respond(self, user_key, user_input) -> Optional[str]:
        user_context = self.user_context_map.get(user_key, None)

        ret = None
        error = []
        if user_context:
            # User is in the middle of conversation

            if user_input == '.abort':
                # If user wishes, abort the current conversation, and remove
                # context data.
                self.user_context_map.pop(user_key)
                return 'Abort current conversation'

            # Check if we can proceed conversation. If user input is irrelevant
            # return help message.
            option = next(
                (o for o in user_context.input_options if o.match(user_input)),
                None)
            if option is None:
                return user_context.help_message

            try:
                ret = option.next_step(CommandMessage(original_text=user_input,
                                                      text=user_input,
                                                      sender=user_key))

                # Only when command is successfully executed, remove current
                # context. To forcefully abort the conversation, use ".abort"
                # command
                self.user_context_map.pop(user_key)
            except Exception as e:
                error.append((option.next_step.__name__, str(e)))

        else:
            # If user is not in the middle of conversation, see if the input
            # text contains command.
            command = self.find_command(user_input)
            if command is None:
                # If it doesn't match any command, leave it.
                return

            try:
                text = re.sub(r'{0}\s+'.format(command.name), '', user_input)
                ret = command.execute(CommandMessage(original_text=user_input,
                                                     text=text,
                                                     sender=user_key))
            except Exception as e:
                error.append((command.name, str(e)))

        if error:
            logging.error('Error occurred. '
                          'command: %s. input: %s. error: %s.' % (
                              error[0][0], user_input, error[0][1]
                          ))
            return 'Something went wrong with "%s"' % user_input

        elif not ret:
            logging.error('command should return UserContext or text'
                          'to let user know the result or next move')
            return 'Something went wrong with "%s"' % user_input

        elif isinstance(ret, UserContext):
            self.user_context_map[user_key] = ret
            return ret.message

        else:
            # String
            return ret

    def find_command(self, text: str) -> Optional[Command]:
        return next((c for c in self.commands if text.startswith(c.name)),
                    None)

    @property
    def schedules(self) -> OrderedDict:
        return self.__schedules.get(self.__class__.__name__, OrderedDict())

    @classmethod
    def schedule(cls, name: str) -> Callable[[CommandFunction], None]:
        def wrapper(func: CommandFunction) -> None:

            @wraps(func)
            def wrapped_function(*args, **kwargs) -> str:
                return func(*args, **kwargs)

            # Register only if bot is instantiated.
            self = cls.__instances.get(cls.__name__, None)
            if self:
                plugin_config = self.plugin_config.get(func.__module__, None)

                if plugin_config is None:
                    logging.warning(
                        'Missing configuration for schedule job. %s. '
                        'Skipping.' % func.__module__)
                else:
                    # If command name duplicates, update with the later one.
                    # The order stays.
                    command = Command(name,
                                      wrapped_function,
                                      func.__module__,
                                      plugin_config)
                    try:
                        # If command is already registered, updated it.
                        idx = [c.name for c in cls.__schedules[cls.__name__]] \
                            .index(command)
                        cls.__schedules[cls.__name__][idx] = command
                    except ValueError:
                        # Not registered, just append it.
                        cls.__schedules[cls.__name__].append(command)

            # To ease plugin's unit test
            return wrapped_function

        return wrapper

    def add_schedule_jobs(self, commands: Sequence[Command]) -> None:
        for command in commands:
            self.add_schedule_job(command)

    @property
    def commands(self) -> OrderedDict:
        return self.__commands.get(self.__class__.__name__, [])

    @classmethod
    def command(cls, name: str) -> Callable[[CommandFunction],
                                            CommandFunction]:

        def wrapper(func: CommandFunction) -> CommandFunction:
            @wraps(func)
            def wrapped_function(*args, **kwargs) -> Union[str, UserContext]:
                return func(*args, **kwargs)

            # Register only if bot is instantiated.
            self = cls.__instances.get(cls.__name__, None)
            if self:
                plugin_config = self.plugin_config.get(func.__module__, {})
                # If command name duplicates, update with the later one.
                # The order stays.

                command = Command(name, func, func.__module__, plugin_config)
                try:
                    # If command is already registered, updated it.
                    idx = [c.name for c in cls.__commands[cls.__name__]] \
                        .index(command)
                    cls.__commands[cls.__name__][idx] = command
                except ValueError:
                    # Not registered, just append it.
                    cls.__commands[cls.__name__].append(command)

            # To ease plugin's unit test
            return wrapped_function

        return wrapper
