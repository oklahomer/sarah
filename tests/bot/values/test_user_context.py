# -*- coding: utf-8 -*-
from assertpy import assert_that

from sarah.bot.values import CommandMessage, CommandConfig, UserContext, \
    InputOption


class DummyClass(object):
    @staticmethod
    def answer_to_yes(msg: CommandMessage, _: CommandConfig) -> str:
        return "That's bad."

    @staticmethod
    def answer_to_no(msg: CommandMessage, _: CommandConfig) -> str:
        return "I doubt it."


class TestUserContext(object):
    def test_valid(self):
        user_context = UserContext(message="Are you sick?",
                                   help_message="Say yes or no.",
                                   input_options=[
                                       InputOption("yes",
                                                   DummyClass.answer_to_yes),
                                       InputOption("no",
                                                   DummyClass.answer_to_no)])

        assert_that(user_context).is_instance_of(UserContext)
        assert_that(user_context.message).is_equal_to("Are you sick?")
        assert_that(user_context.help_message).is_equal_to("Say yes or no.")
        assert_that(user_context.find_next_step("yes"))\
            .is_equal_to(DummyClass.answer_to_yes)
        assert_that(user_context.find_next_step("no")) \
            .is_equal_to(DummyClass.answer_to_no)
        assert_that(user_context.find_next_step("SpamHamEgg")).is_none()
