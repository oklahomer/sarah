# -*- coding: utf-8 -*-
"""Provide basic structure and functionality for bot implementation."""
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
    ScheduledCommand, RichMessage, PluginConfig, CommandFunction, \
    ScheduledFunction
from sarah.thread import ThreadExecutor


class Base(object, metaclass=abc.ABCMeta):
    """Base class of all bot implementation."""

    __commands = {}  # type: Dict[str, List[Command]]
    __schedules = {}  # type: Dict[str, List[ScheduledCommand]]
    __instances = {}  # type: Dict[str, Base] # Should be its subclass

    def __init__(self,
                 plugins: Iterable[PluginConfig] = None,
                 max_workers: Optional[int] = None) -> None:
        """Initializer.

        This may be extended by each bot implementation to do some extra setup,
        but should not be overridden. For the term "extend" and "override,"
        refer to pep257.

        :param plugins: List of plugin modules to import
        :param max_workers: Optional number of worker threads.
            Methods with @concurrent decorator will be submitted to this thread
            pool.
        """
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

        # Running status
        self.running = False

        cls = self.__class__
        cls_name = cls.__name__

        # Reset to ease tests in one file
        cls.__commands[cls_name] = []
        cls.__schedules[cls_name] = []

        # To refer to this instance from class method decorator
        cls.__instances[cls_name] = self

    @abc.abstractmethod
    def generate_schedule_job(self,
                              command: ScheduledCommand) \
            -> Optional[Callable[..., None]]:
        """Generate callback function to be registered to scheduler.

        Since the job handling behaviour varies depending on each bot
        implementation, it is each concrete classes' responsibility to
        generate scheduled job. Returned function will be registered to
        scheduler and will be executed.

        :param command: ScheduledCommand object that holds job information
        :return: Optional callable object to be scheduled
        """
        pass

    @abc.abstractmethod
    def connect(self) -> None:
        """Connect to server.

        Concrete class must override this to establish bot-to-server
        connection. This is called at the end of run() after all setup is done.
        """
        pass

    def run(self) -> None:
        """Start integration with server.

        Based on the settings done in initialization, this will...
            - start workers
            - load plugin modules
            - add scheduled jobs and start scheduler
            - connect to server
        """
        self.running = True

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

    @abc.abstractmethod
    def disconnect(self) -> None:
        pass

    def stop(self) -> None:
        """Stop.

        Concrete class should extend this method to execute each bot specific
        tasks and call this original method to quit everything.
        """
        self.running = False

        logging.info('STOP SCHEDULER')
        if self.scheduler.running:
            try:
                self.scheduler.shutdown()
                logging.info('CANCELLED SCHEDULED WORK')
            except Exception as e:
                logging.error(e)

        logging.info('STOP CONCURRENT WORKER')
        if self.worker:
            self.worker.shutdown(wait=False)

        logging.info('STOP MESSAGE WORKER')
        self.message_worker.shutdown(wait=False)

        self.disconnect()

    @classmethod
    def concurrent(cls, callback_function):
        """A decorator to provide concurrent job mechanism.

        A function wrapped by this decorator will be fed to worker thread pool
        and waits for execution. If max_workers setting is None on
        initialization, thread pool is not created so the given function will
        run immediately.

        Since bot, in nature, requires a lot of I/O bound tasks such as
        retrieving data from 3rd party web API so it is suitable to feed those
        tasks to thread pool. For CPU bound concurrent tasks, consider
        employing multi-process approach.

        :param callback_function: Function to be fed to worker thread pool.
        """
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
        """Submit given callback function to message worker.

        The message_worker is a single-threaded executor, so it is safe to say
        only one message sending task run at a time.

        :param function: Callable to be executed in worker thread.
        :param args: Arguments to be fed to function.
        :param kwargs: Keyword arguments to be fed to function.
        :return: Future object that represent the result of given job.
        """
        return self.message_worker.submit(function, *args, **kwargs)

    def load_plugins(self) -> None:
        """Load given plugin modules."""
        for module_name in self.plugin_config.keys():
            self.load_plugin(module_name)

    @staticmethod
    def load_plugin(module_name: str) -> None:
        """Load given plugin module.

        If the module is already loaded, it reloads to reflect any change.
        """
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
        """Receive user input and respond to it.

        It checks if any UserContext is stored with the given user_key. If
        found, consider this user is in a middle of "conversation" with a
        plugin module. Then the user input is passed to the next_step of that
        UserContext and proceed.

        If there is no UserContext stored, see if any registered command is
        applicable. If found, pass the user input to given plugin module
        command and receive response.

        Command response can be one of UserContext, RichMessage, or string.
        When UserContext is returned, register this context with the user key
        so the next input from the same user can proceed to next step.

        :param user_key: Stringified unique user key. Format varies depending
            on each bot implementation.
        :param user_input: User input text.
        :return: One of RichMessage, string, or None.
        """
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
            next_step = user_context.find_next_step(user_input)
            if next_step is None:
                return user_context.help_message

            try:
                config = self.plugin_config.get(next_step.__module__,
                                                {})
                ret = next_step(CommandMessage(original_text=user_input,
                                               text=user_input,
                                               sender=user_key),
                                config)

                # Only when command is successfully executed, remove current
                # context. To forcefully abort the conversation, use ".abort"
                # command
                self.user_context_map.pop(user_key)
            except Exception as e:
                error.append((next_step.__name__, str(e)))

        else:
            # If user is not in the middle of conversation, see if the input
            # text contains command.
            command = self.find_command(user_input)
            if command is None:
                # If it doesn't match any command, leave it.
                return None

            try:
                text = re.sub(r'{0}\s+'.format(command.name), '', user_input)
                ret = command(CommandMessage(original_text=user_input,
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
        """Receive user input text and return applicable command if any.

        :param text: User input.
        """
        return next((c for c in self.commands if text.startswith(c.name)),
                    None)

    def help(self) -> Union[str, RichMessage]:
        """Return stringified help message.

        Override this method to provide more detailed or rich help message.
        :return: String or RichMessage that contains help message
        """
        return "\n".join(c.help for c in self.commands)

    @property
    def schedules(self) -> List[ScheduledCommand]:
        """Return registered schedules.

        :return: List of ScheduledCommand instances.
        """
        cls = self.__class__
        return cls.__schedules.get(cls.__name__, [])

    @classmethod
    def schedule(cls, name: str) \
            -> Callable[[ScheduledFunction], ScheduledFunction]:
        """A decorator to provide scheduled function.

        When function with this decorator is found on module loading, this
        searches for schedule configuration in the plugin configuration and
        appends the combination of function and the configuration to schedules
        list.

        :param name: Name of the scheduled job.
        :return: Callable that contains registering function. This is to ease
            unit test for plugin modules.
        """
        def wrapper(func: ScheduledFunction) -> ScheduledFunction:
            @wraps(func)
            def wrapped_function(given_config: Dict[str, Any]) \
                    -> Union[str, RichMessage]:
                return func(given_config)

            module = inspect.getmodule(func)
            self = cls.__instances.get(cls.__name__, None)
            # Register only if bot is instantiated.
            if self and module:
                module_name = module.__name__
                config = self.plugin_config.get(module_name, {})
                schedule_config = config.get('schedule', {})
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
                            .index(command.name)
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
        """Add given function to scheduler.

        :param commands: List of ScheduledCommand instances.
        :return: None
        """
        for command in commands:
            # self.add_schedule_job(command)
            job_function = self.generate_schedule_job(command)
            if not job_function:
                continue
            logging.info("Add schedule %s" % command.job_id)
            self.scheduler.add_job(
                job_function,
                id=command.job_id,
                **command.schedule_config.pop(
                    'scheduler_args', {'trigger': "interval",
                                       'minutes': 5}))

    @property
    def commands(self) -> List[Command]:
        """Return registered commands.

        :return: List of Command instances.
        """
        cls = self.__class__
        return cls.__commands.get(cls.__name__, [])

    @classmethod
    def command(cls,
                name: str,
                examples: Iterable[str] = None) \
            -> Callable[[CommandFunction], CommandFunction]:
        """A decorator to provide command function.

        When function with this decorator is found on module loading, this
        searches for configuration in the plugin configuration and appends the
        combination of function and the configuration to commands list.

        :param name: Name of the command.
        :param examples: Optional list of string to be displayed as input
            example.
        :return: Callable that contains registering function. This is to ease
            unit test for plugin modules.
        """
        def wrapper(func: CommandFunction) -> CommandFunction:
            @wraps(func)
            def wrapped_function(command_message: CommandMessage,
                                 given_config: Dict[str, Any]) \
                    -> Union[str, UserContext, RichMessage]:
                return func(command_message, given_config)

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
                        .index(command.name)
                    cls.__commands[cls.__name__][idx] = command
                except ValueError:
                    # Not registered, just append it.
                    cls.__commands[cls.__name__].append(command)

            # To ease plugin's unit test
            return wrapped_function

        return wrapper
