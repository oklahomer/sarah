# -*- coding: utf-8 -*-
from sarah.hipchat import CommandMessage
from sarah.plugins.echo import echo
from sarah.plugins.simple_counter import count, reset_count
from sarah.plugins.bmw_quotes import quote
import sarah.plugins.bmw_quotes


class TestEcho(object):
    def test_valid(self):
        response = echo(CommandMessage(original_text='.echo spam ham',
                                       text='spam ham',
                                       sender='123_homer@localhost/Oklahomer'),
                        {})
        assert response == 'spam ham'


class TestSimpleCounter(object):
    # noinspection PyUnusedLocal
    def setup_method(self, method):
        reset_count(CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='123_homer@localhost/Oklahomer'), {})

    def test_valid(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        response = count(msg, {})
        assert response == str(1)

    def test_multiple_calls_with_same_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        first_response = count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count ham',
                                   text='ham',
                                   sender='other@localhost/Oklahomer')
        other_user_response = count(other_msg, {})
        assert other_user_response == str(1)

        second_response = count(msg, {})
        assert second_response == str(2)

        reset_count(CommandMessage(original_text='.reset_count',
                                   text='',
                                   sender='123_homer@localhost/Oklahomer'), {})

        third_response = count(msg, {})
        assert third_response == str(1)

    def test_multiple_calls_with_different_word(self):
        msg = CommandMessage(original_text='.count ham',
                             text='ham',
                             sender='123_homer@localhost/Oklahomer')
        first_response = count(msg, {})
        assert first_response == str(1)

        other_msg = CommandMessage(original_text='.count spam',
                                   text='spam',
                                   sender='123_homer@localhost/Oklahomer')
        second_response = count(other_msg, {})
        assert second_response == str(1)


class TestBMWQuotes(object):
    def test_valid(self):
        msg = CommandMessage(original_text='.bmw',
                             text='',
                             sender='123_homer@localhost/Oklahomer')
        response = quote(msg, {})
        assert (response in sarah.plugins.bmw_quotes.quotes) is True
