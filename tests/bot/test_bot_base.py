# -*- coding: utf-8 -*-
from typing import Dict, Any
from assertpy import assert_that
from sarah.bot import Base
from sarah.bot.values import CommandMessage, ScheduledCommand, Command


def create_concrete_class():
    # Creates class named "BaseImpl" for test
    return type('BaseImpl',
                (Base,),
                {'connect': lambda self: None,
                 'generate_schedule_job': lambda self: None})


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
        # Concrete class is initialized
        base_impl = create_concrete_class()()

        # Plugin module is loaded while/after initialization
        class BaseImplPlugin(object):
            @staticmethod
            @base_impl.__class__.command(".target", ["spam", "ham"])
            def target_command(msg: CommandMessage, _: Dict) -> str:
                return msg.original_text

        # Then the command provided by plugin module is registered
        registered = base_impl.commands
        assert_that(registered).is_length(1)
        assert_that(registered[0]).is_instance_of(Command)
        assert_that(registered[0](CommandMessage("original message",
                                                 "message",
                                                 "homer"))) \
            .is_equal_to("original message")


class TestScheduleDecorator(object):
    passed_config = None

    def test_decorator(self):
        def func(config: Dict[str, Any]) -> str:
            self.passed_config = config
            return "spam"

        wrapper = Base.schedule("alarm")
        wrapped_function = wrapper(func)
        ret = wrapped_function({'spam': "ham"})

        assert_that(ret).is_equal_to("spam")
        assert_that(self.passed_config).is_not_none()
        assert_that(self.passed_config).is_instance_of(dict)

    def test_with_instance(self):
        # Concrete class is initialized
        base_impl = create_concrete_class()()

        # Scheduler configuration must be set
        schedule_config = {'schedule': {
            'channels': ["Egg"],
            'scheduler_args': {
                'trigger': "cron",
                'hour': 10}}}
        base_impl.plugin_config = {
            'test_bot_base': schedule_config}

        # Plugin module is loaded while/after initialization
        class BaseImplPlugin(object):
            @staticmethod
            @base_impl.__class__.schedule("scheduled_job")
            def scheduled_command(config: Dict) -> str:
                return config

        registered = base_impl.schedules
        assert_that(registered).is_length(1)
        assert_that(registered[0]).is_instance_of(ScheduledCommand)
        assert_that(registered[0]()).is_equal_to(schedule_config)
        assert_that(registered[0].name).is_equal_to("scheduled_job")
        assert_that(registered[0].module_name).is_equal_to("test_bot_base")
        assert_that(registered[0].config).is_equal_to(schedule_config)
        assert_that(registered[0].schedule_config) \
            .is_equal_to(schedule_config["schedule"])
