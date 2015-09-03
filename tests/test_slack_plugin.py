# -*- coding: utf-8 -*-
from assertpy import assert_that
from sarah.bot.slack import SlackMessage
from sarah.bot.values import CommandMessage
from sarah.bot.plugins.bmw_quotes import slack_quote
from sarah.bot.plugins.echo import slack_echo
from sarah.bot.plugins.simple_counter import reset_count, slack_count, \
    slack_reset_count


class TestEcho(object):
    def test_valid(self):
        response = slack_echo(CommandMessage(original_text='.echo spam ham',
                                             text='spam ham',
                                             sender='U06TXXXXX'),
                              {})

        assert_that(response) \
            .described_as(".echo returns user inputs") \
            .is_equal_to("spam ham")


class TestSimpleCounter(object):
    # noinspection PyUnusedLocal
    def setup_method(self, method):
        reset_count('slack')

    def test_valid(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        assert_that(slack_count(msg, {})) \
            .described_as(".count command increments count") \
            .is_equal_to('1')

    def test_multiple_calls_with_same_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        assert_that(slack_count(msg, {})) \
            .described_as("First count returns 1") \
            .is_equal_to('1')

        other_msg = CommandMessage(original_text='.count ham',
                                   text='ham',
                                   sender='U06TYYYYYY')
        assert_that(slack_count(other_msg, {})) \
            .described_as("Different counter for different message") \
            .is_equal_to('1')

        assert_that(slack_count(msg, {})) \
            .described_as("Same message results in incremented count") \
            .is_equal_to('2')

        reset_msg = CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='U06TXXXXX')
        assert_that(slack_reset_count(reset_msg, {})) \
            .described_as(".reset_count command resets current count") \
            .is_equal_to("restart counting")

        assert_that(slack_count(msg, {})) \
            .described_as("Count restarts") \
            .is_equal_to('1')

    def test_multiple_calls_with_different_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        assert_that(slack_count(msg, {})) \
            .described_as("First count message returns 1") \
            .is_equal_to('1')

        other_msg = CommandMessage(original_text='.count spam',
                                   text='spam',
                                   sender='U06TXXXXX')
        assert_that(slack_count(other_msg, {})) \
            .described_as("Second message with different content returns 1") \
            .is_equal_to('1')


class TestBMWQuotes(object):
    def test_valid(self):
        msg = CommandMessage(original_text='.bmw',
                             text='',
                             sender='U06TXXXXX')
        assert_that(slack_quote(msg, {})).is_type_of(SlackMessage)
