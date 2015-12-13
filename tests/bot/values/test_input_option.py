# -*- coding: utf-8 -*-
import re

from assertpy import assert_that

from sarah.bot.values import InputOption, CommandMessage, CommandConfig


class DummyClass(object):
    @staticmethod
    def do_something(msg: CommandMessage, _: CommandConfig) -> str:
        return msg.original_text


class TestInputOption(object):
    def test_init_with_string_pattern(self):
        input_option = InputOption("yes", DummyClass.do_something)

        assert_that(input_option.pattern).is_instance_of(re._pattern_type)
        assert_that(input_option.match("yes")).is_true()
        assert_that(input_option.match("no")).is_false()
        assert_that(input_option.next_step) \
            .is_equal_to(DummyClass.do_something)

    def test_init_with_regexp_pattern(self):
        input_option = InputOption(re.compile("ab*"), DummyClass.do_something)

        assert_that(input_option.pattern).is_instance_of(re._pattern_type)
        assert_that(input_option.match("abcdefg")).is_true()
        assert_that(input_option.match("bbc")).is_false()
        assert_that(input_option.next_step) \
            .is_equal_to(DummyClass.do_something)
