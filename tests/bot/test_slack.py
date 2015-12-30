# -*- coding: utf-8 -*-
import inspect
import json
import logging
import time
from concurrent.futures import Future
from unittest.mock import patch, MagicMock

import pytest
from assertpy import assert_that

import sarah
from sarah.bot.slack import Slack, SlackClient, SarahSlackException, \
    SlackMessage
from sarah.bot.values import ScheduledCommand


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
            .has_ws(None) \
            .has_connect_attempt_count(0)


class TestTryConnect(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        return Slack(token='spam_ham_egg',
                     plugins=(),
                     max_workers=1)

    def test_connection_fail(self, slack):
        with patch.object(slack.client,
                          'request',
                          side_effect=Exception) as mock_connect:
            with pytest.raises(SarahSlackException) as e:
                slack.try_connect()

            assert_that(str(e)).matches("Slack request error on /rtm.start\.")
            assert_that(mock_connect.call_count).is_equal_to(1)

    def test_connection_response_error(self, slack):
        with patch.object(slack.client,
                          'get',
                          return_value={"dummy": "spam"}) as mock_connect:
            with pytest.raises(SarahSlackException) as e:
                slack.try_connect()

            assert_that(mock_connect.call_count).is_equal_to(1)
            assert_that(str(e)).matches("Slack request error on /rtm.start")

    def test_connection_ok(self, slack):
        with patch.object(slack.client,
                          'get',
                          return_value={'url': 'ws://localhost:80/'}):
            with patch.object(sarah.bot.slack.WebSocketApp,
                              'run_forever',
                              return_value=True) as mock_connect:
                slack.try_connect()

                assert_that(mock_connect.call_count).is_equal_to(1)


class TestConnect(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        client = Slack(token='spam_ham_egg',
                       plugins=(),
                       max_workers=1)
        client.running = True
        return client

    def test_reconnection(self, slack):
        logging.error = MagicMock()
        time.sleep = MagicMock()
        with patch.object(slack, "try_connect", side_effect=Exception):
            slack.connect()

            assert_that(slack.try_connect.call_count).is_equal_to(10)
            assert_that(logging.error.call_count).is_equal_to(11)

    def test_disconnect(self, slack):
        slack.ws = MagicMock()
        with patch.object(slack.ws,
                          'close',
                          return_value=None):
            slack.disconnect()
            assert_that(slack.ws.close.call_count).is_equal_to(1)


class TestMessage(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        return Slack(token='spam_ham_egg',
                     plugins=(),
                     max_workers=1)

    def test_fail_reply(self, slack):
        ws = MagicMock()
        logging.error = MagicMock()

        slack.message(ws, json.dumps({'reply_to': "spam", 'ok': False}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_missing_type(self, slack):
        ws = MagicMock()
        logging.error = MagicMock()

        slack.message(ws, json.dumps({}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_invalid_type(self, slack):
        ws = MagicMock()
        logging.error = MagicMock()

        slack.message(ws, json.dumps({'type': "spam.ham.egg"}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_valid_hello(self, slack):
        ws = MagicMock()
        slack.handle_hello = MagicMock()

        slack.message(ws, json.dumps({'type': "hello"}))

        assert_that(slack.handle_hello.call_count).is_equal_to(1)

    def test_valid_message(self, slack):
        ws = MagicMock()
        slack.handle_message = MagicMock()

        slack.message(ws, json.dumps({'type': "message"}))

        assert_that(slack.handle_message.call_count).is_equal_to(1)

    def test_valid_migration(self, slack):
        ws = MagicMock()
        slack.handle_team_migration = MagicMock()

        slack.message(ws, json.dumps({'type': "team_migration_started"}))

        assert_that(slack.handle_team_migration.call_count).is_equal_to(1)


class TestHandleMessage(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        return Slack(token='spam_ham_egg',
                     plugins=(),
                     max_workers=1)

    def test_missing_props(self, slack):
        logging.error = MagicMock()
        slack.respond = MagicMock()
        slack.handle_message({'type': "message",
                              'channel': "my channel",
                              'text': "hello"})

        assert_that(logging.error.call_count).is_equal_to(1)
        assert_that(slack.respond.call_count).is_zero()

    def valid_props_with_simple_response(self, slack):
        with patch.object(slack, "respond", return_value="dummy"):
            with patch.object(slack,
                              "enqueue_sending_message",
                              return_value=Future()):
                slack.handle_message({'type': "message",
                                      'channel': "C06TXXXX",
                                      'user': "U06TXXXXX",
                                      'text': ".bmw",
                                      'ts': "1438477080.000004",
                                      'team': "T06TXXXXX"})
                assert_that(slack.respond.call_count).is_equal_to(1)
                assert_that(slack.enqueue_sending_message.call_count) \
                    .is_equal_to(1)

    def valid_props_with_rich_message_response(self, slack):
        with patch.object(slack, "respond", return_value=SlackMessage()):
            with patch.object(slack.client,
                              "post",
                              return_value=dict()):
                slack.handle_message({'type': "message",
                                      'channel': "C06TXXXX",
                                      'user': "U06TXXXXX",
                                      'text': ".bmw",
                                      'ts': "1438477080.000004",
                                      'team': "T06TXXXXX"})
                assert_that(slack.respond.call_count).is_equal_to(1)
                assert_that(slack.client.post.call_count).is_equal_to(1)


class TestGenerateScheduleJob(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        return Slack(token='',
                     plugins=(),
                     max_workers=1)

    def test_missing_channel_settings(self, slack):
        logging.warning = MagicMock()
        ret = slack.generate_schedule_job(ScheduledCommand("name",
                                                           lambda: "dummy",
                                                           "module_name",
                                                           {},
                                                           {}))

        assert_that(logging.warning.call_count).is_equal_to(1)
        assert_that(ret).is_none()

    def test_valid_settings(self, slack):
        ret = slack.generate_schedule_job(
                ScheduledCommand("name",
                                 lambda _: "dummy",
                                 "module_name",
                                 {},
                                 {'channels': ("channel1",)}))
        assert_that(inspect.isfunction(ret)).is_true()

        with patch.object(slack,
                          "enqueue_sending_message",
                          return_value=Future()):
            ret()
            assert_that(slack.enqueue_sending_message.call_count) \
                .is_equal_to(1)

    def test_valid_settings_with_rich_message(self, slack):
        ret = slack.generate_schedule_job(
                ScheduledCommand("name",
                                 lambda _: SlackMessage(),
                                 "module_name",
                                 {},
                                 {'channels': ("channel1",)}))

        with patch.object(slack.client,
                          "post",
                          return_value=dict()):
            ret()
            assert_that(slack.client.post.call_count) \
                .is_equal_to(1)
