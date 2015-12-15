# -*- coding: utf-8 -*-
from typing import Dict, Any, Callable, Optional

from assertpy import assert_that

from sarah.bot import Base
from sarah.bot.values import CommandMessage, ScheduledCommand, Command


class TestCommandDecorator(object):
    def test_decorator(self):
        self.passed_command_message = None
        self.passed_config = None

        def func(message: CommandMessage, config: Dict[str, Any]) -> str:
            self.passed_command_message = message
            self.passed_config = config
            return "spam"

        wrapper = Base.command(".command_name", [".command_name spam",
                                                 ".command_name ham"])
        wrapped_function = wrapper(func)
        ret = wrapped_function(CommandMessage("original message",
                                              "message", "homer"),
                               {'ham': "egg"})

        assert_that(ret).is_equal_to("spam")

        assert_that(self.passed_command_message).is_not_none()
        assert_that(self.passed_command_message).is_instance_of(CommandMessage)
        assert_that(getattr(self.passed_command_message, "original_text")) \
            .is_equal_to("original message")

        assert_that(self.passed_config).is_not_none()
        assert_that(self.passed_config).is_instance_of(dict)

    def test_with_instance(self):
        class BaseImpl(Base):
            def connect(self) -> None:
                pass

            def generate_schedule_job(self, command: ScheduledCommand) \
                    -> Callable[..., Optional[Any]]:
                pass

        # Implementing class is initialized
        base_impl = BaseImpl()

        # Plugin module is loaded while/after initialization
        class BaseImplPlugin(object):
            @staticmethod
            @BaseImpl.command(".target", ["spam", "ham"])
            def target_command(msg: CommandMessage, _: Dict) -> str:
                return msg.original_text

        # Then the command provided by plugin module is registered
        registered = base_impl.commands
        assert_that(registered).is_length(1)
        assert_that(registered[0]).is_instance_of(Command)
        assert_that(registered[0](CommandMessage("original message",
                                                 "message",
                                                 "homer")))\
            .is_equal_to("original message")
