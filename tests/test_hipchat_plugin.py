# -*- coding: utf-8 -*-
from sarah.plugins.echo import echo
from sarah.plugins.simple_counter import count, reset_count
from sarah.plugins.bmw_quotes import quote
import sarah.plugins.bmw_quotes


class TestEcho(object):
    def test_valid(self):
        response = echo({'original_text': '.echo spam ham',
                         'text': 'spam ham',
                         'from': '123_homer@localhost/Oklahomer'}, {})
        assert response == 'spam ham'


class TestSimpleCounter(object):
    def setup_method(self, method):
        reset_count({'original_text': '.reset_count',
                     'text': '',
                     'from': '123_homer@localhost/Oklahomer'}, {})

    def test_valid(self):
        response = count({'original_text': '.count ham',
                          'text': 'ham',
                          'from': '123_homer@localhost/Oklahomer'}, {})
        assert response == 1

    def test_multiple_calls_with_same_word(self):
        first_response = count({'original_text': '.count ham',
                                'text': 'ham',
                                'from': '123_homer@localhost/Oklahomer'}, {})
        assert first_response == 1

        other_user_response = count({'original_text': '.count ham',
                                     'text': 'ham',
                                     'from': 'other@localhost/Oklahomer'}, {})
        assert other_user_response == 1

        second_response = count({'original_text': '.count ham',
                                 'text': 'ham',
                                 'from': '123_homer@localhost/Oklahomer'}, {})
        assert second_response == 2

        reset_count({'original_text': '.reset_count',
                     'text': '',
                     'from': '123_homer@localhost/Oklahomer'}, {})

        third_response = count({'original_text': '.count ham',
                                'text': 'ham',
                                'from': '123_homer@localhost/Oklahomer'}, {})
        assert third_response == 1

    def test_multiple_calls_with_different_word(self):
        first_response = count({'original_text': '.count ham',
                                'text': 'ham',
                                'from': '123_homer@localhost/Oklahomer'}, {})
        assert first_response == 1

        second_response = count({'original_text': '.count spam',
                                 'text': 'spam',
                                 'from': '123_homer@localhost/Oklahomer'}, {})
        assert second_response == 1


class TestBMWQuotes(object):
    def test_valid(self):
        response = quote({'original_text': '.bmw',
                          'text': '',
                          'from': '123_homer@localhost/Oklahomer'}, {})
        assert (response in sarah.plugins.bmw_quotes.quotes) is True
