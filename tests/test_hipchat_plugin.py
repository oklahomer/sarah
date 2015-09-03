# -*- coding: utf-8 -*-
from assertpy import assert_that
from sarah.bot.values import UserContext, CommandMessage
from sarah.bot.plugins.echo import hipchat_echo
from sarah.bot.plugins.hello import hipchat_hello, hipchat_user_feeling_good, \
    hipchat_user_feeling_bad
from sarah.bot.plugins.simple_counter import hipchat_count, \
    hipchat_reset_count, reset_count
from sarah.bot.plugins.bmw_quotes import hipchat_quote, hipchat_scheduled_quote


class TestEcho(object):
    def test_valid(self):
        response = hipchat_echo(
            CommandMessage(original_text='.echo spam ham',
                           text='spam ham',
                           sender='123_homer@localhost/Oklahomer'),
            {})

        assert_that(response) \
            .described_as(".echo returns user inputs") \
            .is_equal_to("spam ham")


class TestSimpleCounter(object):
    # noinspection PyUnusedLocal
    def setup_method(self, method):
        reset_count('hipchat')

    def test_valid(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_count(msg, {})) \
            .described_as(".count command increments count") \
            .is_equal_to('1')

    def test_multiple_calls_with_same_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_count(msg, {})) \
            .described_as("First count returns 1") \
            .is_equal_to('1')

        other_msg = CommandMessage(original_text='.count ham',
                                   text='ham',
                                   sender='other@localhost/Oklahomer')
        assert_that(hipchat_count(other_msg, {})) \
            .described_as("Different counter for different message") \
            .is_equal_to('1')

        assert_that(hipchat_count(msg, {})) \
            .described_as("Same message results in incremented count") \
            .is_equal_to('2')

        reset_msg = CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_reset_count(reset_msg, {})) \
            .described_as(".reset_count command resets current count") \
            .is_equal_to("restart counting")

        assert_that(hipchat_count(msg, {})) \
            .described_as("Count restarts") \
            .is_equal_to('1')

    def test_multiple_calls_with_different_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_count(msg, {})) \
            .described_as("First count message returns 1") \
            .is_equal_to('1')

        other_msg = CommandMessage(original_text='.count spam',
                                   text='spam',
                                   sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_count(other_msg, {})) \
            .described_as("Second message with different content returns 1") \
            .is_equal_to('1')


class TestBMWQuotes(object):
    def test_valid(self):
        msg = CommandMessage(original_text='.bmw',
                             text='',
                             sender='123_homer@localhost/Oklahomer')
        assert_that(hipchat_quote(msg, {})).is_type_of(str)

    def test_schedule(self):
        assert_that(hipchat_scheduled_quote({})).is_type_of(str)


class TestHello(object):
    def test__init(self):
        msg = CommandMessage(original_text='.hello',
                             text='',
                             sender='spam@localhost/ham')
        response = hipchat_hello(msg, {})

        assert_that(response) \
            .described_as(".hello initiates conversation.") \
            .is_instance_of(UserContext) \
            .has_message("Hello. How are you feeling today?")

        assert_that(response.input_options) \
            .described_as("User has two options to respond.") \
            .is_length(2)

        assert_that([o.next_step.__name__ for o in response.input_options]) \
            .described_as("Those options include 'Good' and 'Bad'") \
            .contains(hipchat_user_feeling_good.__name__,
                      hipchat_user_feeling_bad.__name__)

        assert_that(response.input_options[0].next_step("Good")) \
            .described_as("When 'Good,' just return text.") \
            .is_equal_to("Good to hear that.")

        assert_that(response.input_options[1].next_step("Bad")) \
            .described_as("When 'Bad,' continue to ask health status") \
            .is_instance_of(UserContext)
