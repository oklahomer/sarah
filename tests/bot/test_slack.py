# -*- coding: utf-8 -*-
import inspect
import json
import logging
import time
from concurrent.futures import Future
from unittest.mock import patch, MagicMock, Mock

import pytest
import requests
from assertpy import assert_that
from requests.models import Response
from websocket import WebSocketApp  # type: ignore

import sarah
from sarah.bot.slack import Slack, SlackClient, SarahSlackException, \
    SlackMessage, AttachmentField, MessageAttachment
from sarah.bot.values import ScheduledCommand


class TestSlackClient(object):
    @pytest.fixture(scope='function')
    def client(self, request):
        return SlackClient("dummy_token")

    def test_init_with_default_url(self):
        client = SlackClient("token")
        assert_that(client).has_token("token")
        assert_that(client.base_url).is_not_empty()

    def test_init_with_url(self):
        client = SlackClient("dummy", "http://sample.com/dummy")
        assert_that(client).has_base_url("http://sample.com/dummy")

    def test_generate_endpoint(self, client):
        assert_that(client.generate_endpoint("api.test")) \
            .ends_with("/api.test")

    def test_get(self, client):
        with patch.object(client,
                          "request",
                          return_value={'ok': True}):
            response = client.get("spam")
            assert_that(client.request.call_count).is_equal_to(1)
            assert_that(client.request.call_args[0]).contains("GET", "spam")
            assert_that(response).is_equal_to({'ok': True})

    def test_post(self, client):
        with patch.object(client,
                          "request",
                          return_value={'ok': True}):
            response = client.post("ham", {'key': "val"}, {'foo': "bar"})
            assert_that(client.request.call_count).is_equal_to(1)
            assert_that(client.request.call_args[0]) \
                .contains("POST", "ham", {'key': "val"}, {'foo': "bar"})
            assert_that(response).is_equal_to({'ok': True})

    def test_requet(self, client):
        response = Mock(spec=Response)
        with patch.object(requests,
                          "request",
                          return_value=response):
            with patch.object(response.content,
                              "decode",
                              return_value=json.dumps({'ok': True})):
                ret = client.request("GET", "api.test", {'key': "val"})
                assert_that(requests.request.call_count).is_equal_to(1)
                assert_that(ret).is_equal_to({'ok': True})

    def test_request_exception(self, client):
        logging.error = MagicMock()
        with pytest.raises(Exception):
            with patch.object(requests,
                              "request",
                              side_effect=Exception):
                client.request("GET", "api.test")
                assert_that(logging.error.call_count).is_equal_to(1)


class TestAttachmentField(object):
    def test_to_dict(self):
        kwargs = {'title': "dummy title",
                  'value': "val",
                  'short': True}
        obj = AttachmentField(**kwargs)
        assert_that(obj.to_dict()).is_equal_to(kwargs)


class TestMessageAttachment(object):
    def test_to_dict(self):
        field = AttachmentField("dummy", "val", False)
        kwargs = {'fallback': "string",
                  'title': "my album",
                  'fields': [field]}
        d = MessageAttachment(**kwargs).to_dict()
        assert_that(d['fallback']).is_equal_to("string")
        assert_that(d['title']).is_equal_to("my album")
        assert_that(d['fields']).is_equal_to([field.to_dict()])


class TestSlackMessage(object):
    @pytest.fixture(scope='function')
    def instance(self, request):
        field = AttachmentField("dummy", "val", False)
        attachment = MessageAttachment(fallback="string",
                                       title="my album",
                                       fields=[field])
        return SlackMessage(attachments=[attachment])

    def test_to_dict(self, instance):
        d = instance.to_dict()
        assert_that(d).is_instance_of(dict)
        assert_that(d['attachments']).is_not_empty()

    def test_to_request_params(self, instance):
        p = instance.to_request_params()
        assert_that(p['attachments'][0]).is_instance_of(str)


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


class TestWsCallback(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        client = Slack(token='spam_ham_egg',
                       plugins=(),
                       max_workers=1)
        client.ws = Mock(spec=WebSocketApp)
        return client

    def test_on_error(self, slack):
        logging.error = MagicMock()
        slack.on_error(slack.ws, Exception())
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_on_open(self, slack):
        logging.info = MagicMock()
        slack.on_open(slack.ws)
        assert_that(logging.info.call_count).is_equal_to(1)
        assert_that(logging.info.call_args[0][0]).starts_with("connected")

    def test_on_close(self, slack):
        logging.info = MagicMock()
        slack.on_close(slack.ws, 1000, "normal closure")
        assert_that(logging.info.call_count).is_equal_to(1)
        assert_that(logging.info.call_args[0][0]) \
            .starts_with("connection closed")


class TestMessage(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        client = Slack(token='spam_ham_egg',
                       plugins=(),
                       max_workers=1)
        client.ws = MagicMock()
        return client

    def test_fail_reply(self, slack):
        logging.error = MagicMock()

        slack.message(slack.ws, json.dumps({'reply_to': "spam", 'ok': False}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_missing_type(self, slack):
        logging.error = MagicMock()

        slack.message(slack.ws, json.dumps({}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_invalid_type(self, slack):
        logging.error = MagicMock()

        slack.message(slack.ws, json.dumps({'type': "spam.ham.egg"}))
        assert_that(logging.error.call_count).is_equal_to(1)

    def test_valid_hello(self, slack):
        slack.handle_hello = MagicMock()

        slack.message(slack.ws, json.dumps({'type': "hello"}))

        assert_that(slack.handle_hello.call_count).is_equal_to(1)

    def test_valid_message(self, slack):
        slack.handle_message = MagicMock()

        slack.message(slack.ws, json.dumps({'type': "message"}))

        assert_that(slack.handle_message.call_count).is_equal_to(1)

    def test_handle_team_migration(self, slack):
        logging.info = MagicMock()

        slack.message(slack.ws, json.dumps({'type': "team_migration_started"}))
        assert_that(logging.info.call_count).is_equal_to(1)
        assert_that(logging.info.call_args[0][0]).starts_with("Team migration")

    def test_handle_hello(self, slack):
        logging.info = MagicMock()

        slack.message(slack.ws, json.dumps({'type': "hello"}))
        assert_that(logging.info.call_count).is_equal_to(1)
        assert_that(logging.info.call_args[0][0]) \
            .starts_with("Successfully connected")
        assert_that(slack.connect_attempt_count).is_zero()


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

    def test_props_with_simple_response(self, slack):
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

    def test_props_with_rich_message_response(self, slack):
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


class TestSendMessage(object):
    @pytest.fixture(scope='function')
    def slack(self, request):
        return Slack(token='spam_ham_egg',
                     plugins=(),
                     max_workers=1)

    def test_without_message_type(self, slack):
        slack.ws = MagicMock()
        slack.send_message("spam", "sending text")
        assert_that(slack.ws.send.call_count).is_equal_to(1)
        arg = json.loads(slack.ws.send.call_args[0][0])
        assert_that(arg.get('channel', None)).is_equal_to("spam")
        assert_that(arg.get('text', None)).is_equal_to("sending text")
        assert_that(arg.get('type', None)).is_equal_to("message")
        assert_that(arg.get('id', None)).is_greater_than(0)

    def test_with_message_type(self, slack):
        slack.ws = MagicMock()
        slack.send_message("spam", "sending text", "dummy_type")
        arg = json.loads(slack.ws.send.call_args[0][0])
        assert_that(arg.get('type', None)).is_equal_to("dummy_type")
