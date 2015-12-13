# -*- coding: utf-8 -*-
from assertpy import assert_that

from sarah.bot.values import CommandMessage, Command, CommandConfig


class DummyClass(object):
    @staticmethod
    def answer(msg: CommandMessage, _: CommandConfig) -> str:
        return msg.original_text


class TestCommand(object):
    def test_valid(self):
        command = Command(DummyClass.answer.__name__,
                          DummyClass.answer,
                          DummyClass.__name__,
                          {'spam': "ham"},
                          ["example", "input"])

        assert_that(command.name).is_equal_to(DummyClass.answer.__name__)
        assert_that(command.function).is_equal_to(DummyClass.answer)
        assert_that(command.module_name).is_equal_to(DummyClass.__name__)
        assert_that(command.config).is_equal_to({'spam': "ham"})
        assert_that(command.examples).is_equal_to(["example", "input"])

        # is callable
        assert_that(command(CommandMessage(".hello sarah", "sarah", "homer")))\
            .is_equal_to(".hello sarah")
