# -*- coding: utf-8 -*-
import logging
import types

from assertpy import assert_that

import pytest
from mock import patch, MagicMock, call

import sarah
from sarah.bot.slack import Slack, SlackClient, SarahSlackException


class TestInit(object):
    def test_init(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(),
                      max_workers=1)

        assert_that(slack.client) \
            .described_as("Client module is properly configured") \
            .is_instance_of(SlackClient) \
            .has_token("spam_ham_egg")

        assert_that(slack) \
            .has_message_id(0) \
            .has_ws(None)

    def test_load_plugins(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.bot.plugins.simple_counter', {}),
                               ('sarah.bot.plugins.echo', {})),
                      max_workers=1)
        slack.load_plugins(slack.plugins)

        assert_that(slack.commands.keys()) \
            .described_as("3 commands are loaded") \
            .contains('.count',
                      '.reset_count',
                      '.echo')

        commands = list(slack.commands.values())
        assert_that(commands) \
            .extract('name', 'module_name') \
            .contains_sequence(('.count', 'sarah.bot.plugins.simple_counter'),
                               ('.reset_count',
                                'sarah.bot.plugins.simple_counter'),
                               ('.echo', 'sarah.bot.plugins.echo'))

        for command in commands:
            assert_that(command.function).is_type_of(types.FunctionType)

    def test_non_existing_plugin(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)
        slack.load_plugins(slack.plugins)

        assert_that(slack.commands).is_empty()
        assert_that(slack.scheduler.get_jobs()).is_empty()

    def test_connection_fail(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'request',
                          side_effect=Exception) as mock_connect:
            with pytest.raises(SarahSlackException) as e:
                slack.connect()

            assert_that(str(e)).matches("Slack request error on /rtm.start\.")
            assert_that(mock_connect.call_count).is_equal_to(1)

    def test_connection_response_error(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'get',
                          return_value={"dummy": "spam"}) as mock_connect:
            with pytest.raises(SarahSlackException) as e:
                slack.connect()

            assert_that(mock_connect.call_count).is_equal_to(1)
            assert_that(str(e)).matches("Slack response did not contain "
                                        "connecting url. {'dummy': 'spam'}")

    def test_connection_ok(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'get',
                          return_value={'url': 'ws://localhost:80/'}):
            with patch.object(sarah.bot.slack.WebSocketApp,
                              'run_forever',
                              return_value=True) as mock_connect:
                slack.connect()

                assert_that(mock_connect.call_count).is_equal_to(1)


class TestSchedule(object):
    def test_missing_config(self):
        logging.warning = MagicMock()

        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.bot.plugins.bmw_quotes',),),
                      max_workers=1)
        slack.connect = lambda: True
        slack.run()

        assert_that(slack.scheduler.get_jobs()) \
            .described_as("No module is loaded") \
            .is_empty()
        assert_that(logging.warning.call_count).is_equal_to(1)
        assert_that(logging.warning.call_args) \
            .is_equal_to(call('Missing configuration for schedule job. '
                              'sarah.bot.plugins.bmw_quotes. Skipping.'))

    def test_missing_channel_config(self):
        logging.warning = MagicMock()

        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.bot.plugins.bmw_quotes', {}),),
                      max_workers=1)
        slack.connect = lambda: True
        slack.run()

        assert_that(logging.warning.call_count).is_equal_to(1)
        assert_that(logging.warning.call_args) \
            .is_equal_to(call('Missing channels configuration for schedule '
                              'job. sarah.bot.plugins.bmw_quotes. Skipping.'))

    def test_add_schedule_job(self):
        slack = Slack(
            token='spam_ham_egg',
            max_workers=1,
            plugins=(('sarah.bot.plugins.bmw_quotes',
                      {'channels': 'U06TXXXXX'}),))
        slack.connect = lambda: True
        slack.run()

        jobs = slack.scheduler.get_jobs()
        assert_that(jobs).is_length(1)
        assert_that(jobs[0]).has_id('sarah.bot.plugins.bmw_quotes.bmw_quotes')
        assert_that(jobs[0].trigger).has_interval_length(300)
