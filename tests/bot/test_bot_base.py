# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, Callable

from assertpy import assert_that
from mock import patch, PropertyMock

from sarah.bot import Base
from sarah.bot.values import CommandMessage, ScheduledCommand, Command


def create_concrete_class():
    # Creates class named "BaseImpl" for test
    return type('BaseImpl',
                (Base,),
                {'connect': lambda self: None,
                 'generate_schedule_job': lambda self, command: None})


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

    def test_with_duplicated_assignment(self):
        # Concrete class is initialized
        base_impl = create_concrete_class()()

        # Plugin module is loaded while/after initialization
        class BaseImplPlugin(object):
            @staticmethod
            @base_impl.__class__.command(".target", ["spam", "ham"])
            def target_command(msg: CommandMessage, _: Dict) -> str:
                return msg.original_text

            @staticmethod
            @base_impl.__class__.command(".target", ["spam", "ham"])
            def overriding_command(msg: CommandMessage, _: Dict) -> str:
                return "2ND ASSIGNMENT"

        # Then the command provided by plugin module is registered
        registered = base_impl.commands
        assert_that(registered).is_length(1)
        assert_that(registered[0]).is_instance_of(Command)
        assert_that(registered[0](CommandMessage("original message",
                                                 "message",
                                                 "homer"))) \
            .is_equal_to("2ND ASSIGNMENT")


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

    def test_with_duplicated_assignment(self):
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

            @staticmethod
            @base_impl.__class__.schedule("scheduled_job")
            def overriding_command(config: Dict) -> str:
                return "2ND ASSIGNMENT"

        registered = base_impl.schedules
        assert_that(registered).is_length(1)
        assert_that(registered[0]).is_instance_of(ScheduledCommand)
        assert_that(registered[0]()).is_equal_to("2ND ASSIGNMENT")


class TestAddScheduleJobs(object):
    def test_valid_configuration(self):
        class BaseImpl(Base):
            def connect(self) -> None:
                pass

            def generate_schedule_job(self,
                                      command: ScheduledCommand) \
                    -> Optional[Callable[..., None]]:
                def job_function() -> None:
                    command()

                return job_function

        command = ScheduledCommand('spam',
                                   lambda config: "ham",
                                   'dummy_module_name',
                                   {'egg': "spam"},
                                   {'spam': "egg"})
        base_impl = BaseImpl()
        base_impl.add_schedule_jobs([command])

        assert_that(base_impl.scheduler.get_jobs()).is_length(1)
        registered_job = base_impl.scheduler.get_job(command.job_id)
        assert_that(registered_job).is_not_none()

    def test_missing_returning_function(self):
        class BaseImpl(Base):
            def connect(self) -> None:
                pass

            def generate_schedule_job(self,
                                      command: ScheduledCommand) \
                    -> Optional[Callable[..., None]]:
                return None

        command = ScheduledCommand('spam',
                                   lambda config: "ham",
                                   'dummy_module_name',
                                   {'egg': "spam"},
                                   {'spam': "egg"})
        base_impl = BaseImpl()
        base_impl.add_schedule_jobs([command])

        assert_that(base_impl.scheduler.get_jobs()).is_empty()


class TestHelp(object):
    def test_with_examples(self):
        base_impl = create_concrete_class()()
        assert_that(base_impl.help()).is_empty()

        commands = [Command(
                "command%d" % i,
                lambda msg, config: "foo",
                "module_name%d" % i,
                {'spam': "ham"},
                ["example1 %d" % i, "example2 %d" % i]) for i in range(10)]

        with patch.object(base_impl.__class__,
                          'commands',
                          new_callable=PropertyMock) as m:
            m.return_value = commands
            assert_that(base_impl.help()) \
                .is_equal_to("\n".join(c.help for c in commands))


class TestFindCommand(object):
    def test_valid(self):
        base_impl = create_concrete_class()()

        def dummy_func(msg, _):
            return msg.original_text

        irrelevant_command = Command(".matching",
                                     dummy_func,
                                     "matching_module",
                                     {'spam': "ham"})
        matching_command = Command(".matching",
                                   dummy_func,
                                   "matching_module",
                                   {'spam': "ham"})

        with patch.object(base_impl.__class__,
                          'commands',
                          new_callable=PropertyMock) as m:
            m.return_value = [irrelevant_command, matching_command]
            assert_that(base_impl.find_command(".SPAM_HAM_EGG")).is_none()
            assert_that(base_impl.find_command(".matching")) \
                .is_equal_to(matching_command)
