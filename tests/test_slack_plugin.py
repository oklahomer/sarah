# -*- coding: utf-8 -*-
from sarah import CommandMessage
from sarah.plugins.bmw_quotes import slack_quote
from sarah.plugins.echo import slack_echo
from sarah.plugins.simple_counter import reset_count, slack_count, \
    slack_reset_count
import sarah.plugins.bmw_quotes


class TestEcho(object):
    def test_valid(self):
        response = slack_echo(CommandMessage(original_text='.echo spam ham',
                                             text='spam ham',
                                             sender='U06TXXXXX'),
                              {})
        assert response == 'spam ham'


class TestSimpleCounter(object):
    # noinspection PyUnusedLocal
    def setup_method(self, method):
        reset_count('slack')

    def test_valid(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        response = slack_count(msg, {})
        assert response == str(1)

    def test_multiple_calls_with_same_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        first_response = slack_count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count ham',
                                   text='ham',
                                   sender='U06TYYYYYY')
        other_user_response = slack_count(other_msg, {})
        assert other_user_response == str(1)

        second_response = slack_count(msg, {})
        assert second_response == str(2)

        reset_msg = CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='U06TXXXXX')
        slack_reset_count(reset_msg, {})

        third_response = slack_count(msg, {})
        assert third_response == str(1)

    def test_multiple_calls_with_different_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='U06TXXXXX')
        first_response = slack_count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count spam',
                                   text='spam',
                                   sender='U06TXXXXX')
        second_response = slack_count(other_msg, {})
        assert second_response == str(1)


class TestBMWQuotes(object):
    def test_valid(self):
        msg = CommandMessage(original_text='.bmw',
                             text='',
                             sender='U06TXXXXX')
        response = slack_quote(msg, {})
        assert (response in sarah.plugins.bmw_quotes.quotes) is True
