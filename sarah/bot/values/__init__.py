# -*- coding: utf-8 -*-
import abc
import re

from typing import Union, Pattern, AnyStr, Callable, Dict, Iterable, Any, \
    Optional, Match, Tuple

from sarah import ValueObject


class RichMessage(ValueObject, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __str__(self) -> str:
        pass


class InputOption(ValueObject):
    def __init__(self,
                 pattern: Union[Pattern, AnyStr],
                 next_step: Callable[..., Optional[Any]]) -> None:
        if isinstance(pattern, str):
            self['pattern'] = re.compile(pattern)

    @property
    def pattern(self) -> Pattern:
        return self['pattern']

    @property
    def next_step(self) -> Callable[..., Optional[Any]]:
        return self['next_step']

    def match(self, msg: str) -> Match[Any]:
        return self.pattern.match(msg)


class UserContext(ValueObject):
    def __init__(self,
                 message: Union[str, RichMessage],
                 help_message: str,
                 input_options: Iterable[InputOption]) -> None:
        pass

    def __str__(self):
        return str(self.message)

    @property
    def message(self) -> Union[str, RichMessage]:
        return self['message']

    @property
    def help_message(self) -> str:
        return self['help_message']

    @property
    def input_options(self) -> Iterable[InputOption]:
        return self['input_options']


class CommandMessage(ValueObject):
    def __init__(self, original_text: str, text: str, sender: str) -> None:
        pass

    @property
    def original_text(self) -> str:
        return self['original_text']

    @property
    def text(self) -> str:
        return self['text']

    @property
    def sender(self) -> str:
        return self['sender']


CommandFunction = Callable[
    ...,
    Union[str, RichMessage, UserContext]]

CommandConfig = Dict[str, Any]


class Command(ValueObject):
    def __init__(self,
                 name: str,
                 function: CommandFunction,
                 module_name: str,
                 config: CommandConfig,
                 examples: Iterable[str] = None) -> None:
        pass

    @property
    def name(self):
        return self['name']

    @property
    def function(self):
        return self['function']

    @property
    def module_name(self):
        return self['module_name']

    @property
    def config(self):
        return self['config']

    @property
    def examples(self):
        return self['examples']

    def execute(self, command_message: CommandMessage) \
            -> Union[UserContext, RichMessage, str]:
        return self.function(command_message, self.config)


ScheduledFunction = Callable[..., Union[str, RichMessage]]


class ScheduledCommand(ValueObject):
    # noinspection PyMissingConstructor
    def __init__(self,
                 name: str,
                 function: ScheduledFunction,
                 module_name: str,
                 config: CommandConfig,
                 schedule_config: Dict) -> None:
        pass

    @property
    def name(self):
        return self['name']

    @property
    def function(self):
        return self['function']

    @property
    def module_name(self):
        return self['module_name']

    @property
    def config(self):
        return self['config']

    @property
    def schedule_config(self) -> Dict:
        return self['schedule_config']

    def execute(self) -> Union[RichMessage, str]:
        return self.function(self.config)


PluginConfig = Tuple[str, Optional[Dict]]
