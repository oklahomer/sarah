# -*- coding: utf-8 -*-
import abc
import imp
import importlib
import inspect
import logging
import re
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future  # type: ignore
from functools import wraps

from apscheduler.schedulers import background  # type: ignore
from typing import Optional, Callable, Union, Iterable, List, Any
from sarah.bot.types import PluginConfig, ScheduledFunction, CommandFunction

try:
    from typing import Dict, Tuple

    # Work-around to avoid pyflakes warning "imported but unused" regarding
    # mypy's comment-styled type hinting
    # http://www.laurivan.com/make-pyflakespylint-ignore-unused-imports/
    # http://stackoverflow.com/questions/5033727/how-do-i-get-pyflakes-to-ignore-a-statement/12121404#12121404
    assert Dict
    assert Tuple
except AssertionError:
    pass

from sarah.bot.values import Command, CommandMessage, UserContext, \
    ScheduledCommand, RichMessage
from sarah.thread import ThreadExecutor


class Base(object, metaclass=abc.ABCMeta):
    __commands = {}  # type: Dict[str, List[Command]]
    __schedules = {}  # type: Dict[str, List[ScheduledCommand]]
    __instances = {}  # type: Dict[str, Base] # Should be its subclass

    def __init__(self,
                 plugins: Iterable[PluginConfig] = None,
                 max_workers: Optional[int] = None) -> None:
        if not plugins:
            plugins = ()

        # {module_name: config, ...}
        # Some simple plugins can be used without configuration, so second
        # element may be omitted on assignment.
        # In that case, just give empty dictionary as configuration value.
        self.plugin_config = OrderedDict(
            [(p[0], p[1] if len(p) > 1 else {}) for p in plugins])

        self.max_workers = max_workers
        self.scheduler = background.BackgroundScheduler()
        self.user_context_map = {}  # type: Dict[str, UserContext]

        # To be set on run()
        self.worker = None  # type: ThreadPoolExecutor
        self.message_worker = None  # type: ThreadExecutor

        # Reset to ease tests in one file
        self.__commands[self.__class__.__name__] = []
        self.__schedules[self.__class__.__name__] = []

        # To refer to this instance from class method decorator
        self.__instances[self.__class__.__name__] = self

    @abc.abstractmethod
    def generate_schedule_job(self,
                              command: ScheduledCommand)\
            -> Callable[..., Optional[Any]]:
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
        self.load_plugins()

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

    def enqueue_sending_message(self, function, *args, **kwargs) -> Future:
        return self.message_worker.submit(function, *args, **kwargs)

    def load_plugins(self) -> None:
        for module_name in self.plugin_config.keys():
            self.load_plugin(module_name)

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

    def respond(self,
                user_key: str,
                user_input: str) -> Optional[Union[RichMessage, str]]:
        user_context = self.user_context_map.get(user_key, None)

        if user_input == '.help':
            return self.help()

        ret = None  # type: Optional[Union[RichMessage, UserContext, str]]
        error = []  # type: List[Tuple[str, str]]
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
                config = self.plugin_config.get(option.next_step.__module__,
                                                {})
                ret = option.next_step(CommandMessage(original_text=user_input,
                                                      text=user_input,
                                                      sender=user_key),
                                       config)

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
                return None

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
            # String or RichMessage
            return ret

    def find_command(self, text: str) -> Optional[Command]:
        return next((c for c in self.commands if text.startswith(c.name)),
                    None)

    # Override this method to display rich help message
    def help(self) -> str:
        return "\n".join(
            [(c.name + ": " + ", ".join(c.examples) if c.examples else c.name)
             for c in self.commands])

    @property
    def schedules(self) -> List[ScheduledCommand]:
        return self.__schedules.get(self.__class__.__name__, [])

    @classmethod
    def schedule(cls, name: str) -> Callable[[ScheduledFunction], None]:
        def wrapper(func: ScheduledFunction) -> None:

            @wraps(func)
            def wrapped_function(*args, **kwargs) -> Union[str, RichMessage]:
                return func(*args, **kwargs)

            module = inspect.getmodule(func)
            self = cls.__instances.get(cls.__name__, None)
            # Register only if bot is instantiated.
            if self and module:
                module_name = module.__name__
                config = self.plugin_config.get(module_name, {})
                schedule_config = config.get('schedule', None)
                if schedule_config:
                    # If command name duplicates, update with the later one.
                    # The order stays.
                    command = ScheduledCommand(name,
                                               wrapped_function,
                                               module_name,
                                               config,
                                               schedule_config)
                    try:
                        # If command is already registered, updated it.
                        idx = [c.name for c in cls.__schedules[cls.__name__]] \
                            .index(command)
                        cls.__schedules[cls.__name__][idx] = command
                    except ValueError:
                        # Not registered, just append it.
                        cls.__schedules[cls.__name__].append(command)
                else:
                    logging.warning(
                        'Missing configuration for schedule job. %s. '
                        'Skipping.' % module_name)

            # To ease plugin's unit test
            return wrapped_function

        return wrapper

    def add_schedule_jobs(self, commands: Iterable[ScheduledCommand]) -> None:
        for command in commands:
            # self.add_schedule_job(command)
            job_function = self.generate_schedule_job(command)
            if not job_function:
                continue
            job_id = '%s.%s' % (command.module_name, command.name)
            logging.info("Add schedule %s" % job_id)
            self.scheduler.add_job(
                job_function,
                id=job_id,
                **command.schedule_config.pop(
                    'scheduler_args', {'trigger': "interval",
                                       'minutes': 5}))

    @property
    def commands(self) -> List[Command]:
        return self.__commands.get(self.__class__.__name__, [])

    @classmethod
    def command(cls,
                name: str,
                examples: Iterable[str] = None) \
            -> Callable[[CommandFunction], CommandFunction]:

        def wrapper(func: CommandFunction) -> CommandFunction:
            @wraps(func)
            def wrapped_function(*args, **kwargs) \
                    -> Union[str, UserContext, RichMessage]:
                return func(*args, **kwargs)

            module = inspect.getmodule(func)
            self = cls.__instances.get(cls.__name__, None)
            # Register only if bot is instantiated.
            if self and module:
                module_name = module.__name__
                config = self.plugin_config.get(module_name, {})
                # If command name duplicates, update with the later one.
                # The order stays.

                command = Command(name, func, module_name, config, examples)
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
