# -*- coding: utf-8 -*-
from sarah import CommandMessage
from sarah.plugins.echo import hipchat_echo
from sarah.plugins.simple_counter import hipchat_count, hipchat_reset_count, \
    reset_count
from sarah.plugins.bmw_quotes import hipchat_quote
import sarah.plugins.bmw_quotes


class TestEcho(object):
    def test_valid(self):
        response = hipchat_echo(
            CommandMessage(original_text='.echo spam ham',
                           text='spam ham',
                           sender='123_homer@localhost/Oklahomer'),
            {})
        assert response == 'spam ham'


class TestSimpleCounter(object):
    # noinspection PyUnusedLocal
    def setup_method(self, method):
        reset_count('hipchat')

    def test_valid(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        response = hipchat_count(msg, {})
        assert response == str(1)

    def test_multiple_calls_with_same_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        first_response = hipchat_count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count ham',
                                   text='ham',
                                   sender='other@localhost/Oklahomer')
        other_user_response = hipchat_count(other_msg, {})
        assert other_user_response == str(1)

        second_response = hipchat_count(msg, {})
        assert second_response == str(2)

        reset_msg = CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='123_homer@localhost/Oklahomer')
        hipchat_reset_count(reset_msg, {})

        third_response = hipchat_count(msg, {})
        assert third_response == str(1)

    def test_multiple_calls_with_different_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        first_response = hipchat_count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count spam',
                                   text='spam',
                                   sender='123_homer@localhost/Oklahomer')
        second_response = hipchat_count(other_msg, {})
        assert second_response == str(1)


class TestBMWQuotes(object):
    def test_valid(self):
        msg = CommandMessage(original_text='.bmw',
                             text='',
                             sender='123_homer@localhost/Oklahomer')
        response = hipchat_quote(msg, {})
        assert (response in sarah.plugins.bmw_quotes.quotes) is True
