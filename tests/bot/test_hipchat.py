# -*- coding: utf-8 -*-
import concurrent
import inspect
import logging
from concurrent.futures import ALL_COMPLETED, Future
from time import sleep

import pytest
from assertpy import assert_that
from mock import MagicMock, call, patch
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqTimeout, IqError
from sleekxmpp.stanza import Message
from sleekxmpp.test import TestSocket
from sleekxmpp.xmlstream import JID

import sarah.bot.hipchat
from sarah.bot.hipchat import HipChat, SarahHipChatException

# noinspection PyProtectedMember
from sarah.bot.values import ScheduledCommand


class MockXMPP(ClientXMPP):
    def __init__(self, *args):
        super().__init__(*args, sasl_mech=None)
        self._id_prefix = ''
        self._disconnect_wait_for_threads = False
        self.default_lang = None
        self.peer_default_lang = None
        self.set_socket(TestSocket())
        self.auto_reconnect = False
        self.state._set_state('connect')
        self.socket.recv_data(self.stream_header)
        self.use_message_ids = False


sarah.bot.hipchat.ClientXMPP = MockXMPP


# noinspection PyUnresolvedReferences
class TestInit(object):
    def test_init(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          rooms=['123_homer@localhost'],
                          plugins=(),
                          proxy={'host': 'localhost',
                                 'port': 1234,
                                 'username': 'homers',
                                 'password': 'mypassword'})

        # This doesn't work with assertpy.
        # Does this have something to do with ABCMeta?
        # assert_that(hipchat).is_instance_of(HipChat)
        assert isinstance(hipchat, HipChat) is True

        assert_that(hipchat) \
            .has_nick('Sarah') \
            .has_rooms(['123_homer@localhost'])

        assert_that(hipchat.client) \
            .is_instance_of(ClientXMPP) \
            .has_use_proxy(True) \
            .has_proxy_config({'host': 'localhost',
                               'port': 1234,
                               'username': 'homers',
                               'password': 'mypassword'})

        assert_that(hipchat.client.requested_jid) \
            .is_not_none() \
            .is_instance_of(JID) \
            .is_equal_to(JID('test@localhost', cache_lock=True))


class TestConnect(object):
    def test_connection_fail(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password')

        with patch.object(
                hipchat.client,
                'connect',
                return_value=False) as mock_connect:
            with pytest.raises(SarahHipChatException) as e:
                hipchat.run()

            assert_that(str(e)) \
                .matches("Couldn't connect to server\.")
            assert_that(mock_connect.call_count).is_equal_to(1)


# noinspection PyUnresolvedReferences
class TestMessage(object):
    @pytest.fixture(scope='function')
    def hipchat(self, request):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=None,
                    max_workers=4)
        h.client.connect = lambda: True
        h.client.process = lambda *args, **kwargs: True
        request.addfinalizer(h.stop)
        h.run()

        return h

    def wait_future_finish(self, future):
        sleep(.5)  # Why would I need this line?? Check later.

        ret = concurrent.futures.wait([future], 5, return_when=ALL_COMPLETED)
        if len(ret.not_done) > 0:
            logging.error("Jobs are not finished.")
        assert_that(ret.done).contains(future)

    def test_skip_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = 'test body'

        msg.reply = MagicMock()

        with patch.object(hipchat, 'respond', return_value=None):
            self.wait_future_finish(hipchat.message(msg))
            assert_that(msg.reply.call_count).is_equal_to(0)

    def test_skip_own_message(self, hipchat):
        msg = Message(hipchat.client, stype='groupchat')
        msg['body'] = 'test body'

        hipchat.respond = MagicMock()

        with patch.object(msg, "get_mucroom", return_value="abc"):
            with patch.dict(hipchat.client.plugin['xep_0045'].ourNicks,
                            {'abc': "homer"},
                            clear=True):
                with patch.object(msg, "get_mucnick", return_value="homer"):
                    self.wait_future_finish(hipchat.message(msg))
                    assert_that(hipchat.respond.call_count).is_equal_to(0)

    def test_echo_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = '.echo spam'

        msg.reply = MagicMock()

        with patch.object(hipchat, 'respond', return_value="spam"):
            self.wait_future_finish(hipchat.message(msg))
            assert_that(hipchat.respond.call_count).is_equal_to(1)
            assert_that(msg.reply.call_count).is_equal_to(1)
            assert_that(msg.reply.call_args).is_equal_to(call('spam'))


class TestGenerateScheduleJob(object):
    @pytest.fixture(scope='function')
    def hipchat(self, request):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=None,
                    max_workers=4)

        return h

    def test_missing_room_settings(self, hipchat):
        with patch.object(logging,
                          'warning',
                          return_value=None):
            ret = hipchat.generate_schedule_job(
                    ScheduledCommand("name",
                                     lambda: "dummy",
                                     "module_name",
                                     {},
                                     {}))

            assert_that(logging.warning.call_count).is_equal_to(1)
            assert_that(ret).is_none()

    def test_valid_settings(self, hipchat):
        ret = hipchat.generate_schedule_job(
                ScheduledCommand("name",
                                 lambda _: "dummy",
                                 "module_name",
                                 {},
                                 {'rooms': ("room1",)}))
        assert_that(inspect.isfunction(ret)).is_true()

        with patch.object(hipchat,
                          "enqueue_sending_message",
                          return_value=Future()):
            ret()
            assert_that(hipchat.enqueue_sending_message.call_count) \
                .is_equal_to(1)


# noinspection PyUnresolvedReferences
class TestSessionStart(object):
    # noinspection PyUnusedLocal
    @pytest.fixture
    def hipchat(self, request):
        # NO h.start() for this test
        return HipChat(nick='Sarah',
                       jid='test@localhost',
                       password='password',
                       plugins=())

    def throw_iq_timeout(self):
        raise IqTimeout(None)

    def throw_iq_error(self):
        raise IqError({'error': {'condition': 'ham',
                                 'text': 'egg',
                                 'type': 'spam'}})

    def throw_exception(self):
        raise Exception('spam.ham.egg')

    def test_timeout(self, hipchat):
        with patch.object(hipchat.client, 'send_presence', return_value=None):
            with patch.object(
                    hipchat.client,
                    'get_roster',
                    side_effect=self.throw_iq_timeout) as mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert_that(mock_get_roster.call_count).is_equal_to(1)
                assert_that(str(e)) \
                    .matches('Timeout occurred while getting roster. '
                             'Error type: cancel. '
                             'Condition: remote-server-timeout.')

    def test_unknown_error(self, hipchat):
        with patch.object(hipchat.client, 'send_presence', return_value=None):
            with patch.object(
                    hipchat.client,
                    'get_roster',
                    side_effect=self.throw_exception) as mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert_that(mock_get_roster.call_count).is_equal_to(1)
                assert_that(str(e)) \
                    .matches('Unknown error occurred: spam.ham.egg.')

    def test_iq_error(self, hipchat):
        with patch.object(hipchat.client, 'send_presence', return_value=None):
            with patch.object(
                    hipchat.client,
                    'get_roster',
                    side_effect=self.throw_iq_error) as mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert_that(mock_get_roster.call_count).is_equal_to(1)
                assert_that(str(e)) \
                    .matches('IQError while getting roster. '
                             'Error type: spam. '
                             'Condition: ham. Content: egg.')


# noinspection PyUnresolvedReferences
class TestJoinRooms(object):
    def test_success(self):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    rooms=['123_homer@localhost'],
                    password='password',
                    plugins=())

        with patch.object(h.client.plugin['xep_0045'].xmpp,
                          'send',
                          return_value=None) as mock_send:
            h.join_rooms({})

            assert_that(mock_send.call_count).is_equal_to(1)
            assert_that(h.client.plugin['xep_0045']) \
                .has_rooms({'123_homer@localhost': {}}) \
                .has_ourNicks({'123_homer@localhost': h.nick})

    def test_no_setting(self):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=())

        with patch.object(h.client.plugin['xep_0045'].xmpp,
                          'send',
                          return_value=None) as mock_send:
            h.join_rooms({})

            assert_that(mock_send.call_count).is_equal_to(0)
            assert_that(h.client.plugin['xep_0045']) \
                .has_rooms({}) \
                .has_ourNicks({})
