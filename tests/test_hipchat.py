# -*- coding: utf-8 -*-
import concurrent
from concurrent.futures import ALL_COMPLETED
from time import sleep
import logging
import types

import pytest
from apscheduler.triggers.interval import IntervalTrigger
from sleekxmpp import ClientXMPP
from sleekxmpp.test import TestSocket
from sleekxmpp.stanza import Message
from sleekxmpp.exceptions import IqTimeout, IqError
from sleekxmpp.xmlstream import JID
from mock import MagicMock, call, patch

from sarah.bot import CommandMessage, UserContext
from sarah.bot.hipchat import HipChat, SarahHipChatException
import sarah.bot.plugins.simple_counter


# noinspection PyProtectedMember
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
                          plugins=(('sarah.bot.plugins.simple_counter', {}),
                                   ('sarah.bot.plugins.echo', {})),
                          proxy={'host': 'localhost',
                                 'port': 1234,
                                 'username': 'homers',
                                 'password': 'mypassword'})

        assert hipchat.nick == 'Sarah'
        assert hipchat.rooms == ['123_homer@localhost']
        assert hipchat.client.requested_jid == JID('test@localhost',
                                                   cache_lock=True)

        assert isinstance(hipchat, HipChat) is True
        assert isinstance(hipchat.client, ClientXMPP) is True

        assert hipchat.client.use_proxy is True
        assert hipchat.client.proxy_config == {'host': 'localhost',
                                               'port': 1234,
                                               'username': 'homers',
                                               'password': 'mypassword'}

    def test_load_plugins(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.simple_counter', {}),
                                   ('sarah.bot.plugins.echo', {})),
                          proxy={'host': 'localhost',
                                 'port': 1234,
                                 'username': 'homers',
                                 'password': 'mypassword'})

        hipchat.load_plugins(hipchat.plugins)

        assert list(hipchat.commands.keys()) == ['.count',
                                                 '.reset_count',
                                                 '.echo']

        commands = list(hipchat.commands.values())

        assert commands[0].name == '.count'
        assert commands[0].module_name == 'sarah.bot.plugins.simple_counter'
        assert isinstance(commands[0].function, types.FunctionType) is True

        assert commands[1].name == '.reset_count'
        assert commands[1].module_name == 'sarah.bot.plugins.simple_counter'
        assert isinstance(commands[1].function, types.FunctionType) is True

        assert commands[2].name == '.echo'
        assert commands[2].module_name == 'sarah.bot.plugins.echo'
        assert isinstance(commands[2].function, types.FunctionType) is True

    def test_non_existing_plugin(self):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=(('spam.ham.egg.onion', {}),))
        h.load_plugins(h.plugins)
        assert len(h.commands) == 0
        assert len(h.scheduler.get_jobs()) == 0

    def test_connection_fail(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password')

        with patch.object(
                hipchat.client,
                'connect',
                return_value=False) as _mock_connect:
            with pytest.raises(SarahHipChatException) as e:
                hipchat.run()

            assert e.value.args[0] == 'Couldn\'t connect to server.'
            assert _mock_connect.call_count == 1

    def test_run(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password')

        with patch.object(hipchat.client, 'connect', return_value=True):
            with patch.object(
                    hipchat.client,
                    'process',
                    return_value=True) as mock_client_process:
                hipchat.run()

                assert mock_client_process.call_count == 1
                assert hipchat.scheduler.running is True


# noinspection PyUnresolvedReferences
class TestFindCommand(object):
    # noinspection PyUnusedLocal
    @pytest.fixture
    def hipchat(self, request):
        # NO h.start() for this test
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=(('sarah.bot.plugins.simple_counter',
                              {'spam': 'ham'}),
                             ('sarah.bot.plugins.echo',)))
        h.load_plugins(h.plugins)
        return h

    def test_no_corresponding_command(self, hipchat):
        command = hipchat.find_command('egg')
        assert command is None

    def test_echo(self, hipchat):
        command = hipchat.find_command('.echo spam ham')
        assert command.config == {}
        assert command.name == '.echo'
        assert command.module_name == 'sarah.bot.plugins.echo'
        assert isinstance(command.function, types.FunctionType) is True

    def test_count(self, hipchat):
        command = hipchat.find_command('.count spam')
        assert command.config == {'spam': 'ham'}
        assert command.name == '.count'
        assert command.module_name == 'sarah.bot.plugins.simple_counter'
        assert isinstance(command.function, types.FunctionType) is True


# noinspection PyUnresolvedReferences
class TestMessage(object):
    @pytest.fixture(scope='function')
    def hipchat(self, request):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=(('sarah.bot.plugins.hello', {}),
                             ('sarah.bot.plugins.simple_counter', {}),
                             ('sarah.bot.plugins.echo',)),
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
        assert future in ret.done

    def test_skip_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = 'test body'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert msg.reply.call_count == 0

    def test_echo_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = '.echo spam'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert msg.reply.call_count == 1
        assert msg.reply.call_args == call('spam')

    def test_count_message(self, hipchat):
        msg = Message(hipchat.client,
                      stype='normal',
                      sfrom='123_homer@localhost/Oklahomer')
        msg['body'] = '.count ham'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert msg.reply.call_count == 1
        assert msg.reply.call_args == call('1')

        self.wait_future_finish(hipchat.message(msg))
        assert msg.reply.call_count == 2
        assert msg.reply.call_args == call('2')

        msg['body'] = '.count egg'
        self.wait_future_finish(hipchat.message(msg))
        assert msg.reply.call_count == 3
        assert msg.reply.call_args == call('1')

        stash = vars(sarah.bot.plugins.simple_counter).get(
            '__stash', {}).get('hipchat', {})
        assert stash == {'123_homer@localhost/Oklahomer': {'ham': 2, 'egg': 1}}

    def test_conversation(self, hipchat):
        user_key = '123_homer@localhost/Oklahomer'

        # Initial message
        assert (hipchat.respond(user_key, '.hello') ==
                "Hello. How are you feeling today?")

        # Context is set
        assert isinstance(hipchat.user_context_map.get(user_key), UserContext)

        # Wrong formatted message results with help message
        assert (hipchat.respond(user_key, "SomeBizarreText") ==
                "Say Good or Bad, please.")

        assert (hipchat.respond(user_key, "Bad") ==
                "Are you sick?")

        # Still in conversation
        assert isinstance(hipchat.user_context_map.get(user_key), UserContext)

        # The last yes/no question
        assert hipchat.respond(user_key, "Yes")

        # Context is removed
        assert hipchat.user_context_map.get(user_key) is None


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
                    side_effect=self.throw_iq_timeout) as _mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert _mock_get_roster.call_count == 1
                assert e.value.args[0] == (
                    'Timeout occurred while getting roster. '
                    'Error type: cancel. '
                    'Condition: remote-server-timeout.')

    def test_unknown_error(self, hipchat):
        with patch.object(hipchat.client, 'send_presence', return_value=None):
            with patch.object(
                    hipchat.client,
                    'get_roster',
                    side_effect=self.throw_exception) as _mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert _mock_get_roster.call_count == 1
                assert e.value.args[0] == (
                    'Unknown error occurred: spam.ham.egg.')

    def test_iq_error(self, hipchat):
        with patch.object(hipchat.client, 'send_presence', return_value=None):
            with patch.object(
                    hipchat.client,
                    'get_roster',
                    side_effect=self.throw_iq_error) as _mock_get_roster:
                with pytest.raises(SarahHipChatException) as e:
                    hipchat.session_start(None)

                assert _mock_get_roster.call_count == 1
                assert e.value.args[0] == (
                    'IQError while getting roster. '
                    'Error type: spam. Condition: ham. Content: egg.')


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
                          return_value=None) as _mock_send:
            h.join_rooms({})

            assert _mock_send.call_count == 1
            assert h.client.plugin['xep_0045'].rooms == {
                '123_homer@localhost': {}}
            assert h.client.plugin['xep_0045'].ourNicks == {
                '123_homer@localhost': h.nick}

    def test_no_setting(self):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=())

        with patch.object(h.client.plugin['xep_0045'].xmpp,
                          'send',
                          return_value=None) as _mock_send:
            h.join_rooms({})

            assert _mock_send.call_count == 0
            assert h.client.plugin['xep_0045'].rooms == {}
            assert h.client.plugin['xep_0045'].ourNicks == {}


# noinspection PyUnresolvedReferences
class TestSchedule(object):
    def test_missing_config(self):
        logging.warning = MagicMock()

        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.bmw_quotes',),))
        hipchat.connect = lambda: True
        hipchat.run()

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
            'Missing configuration for schedule job. '
            'sarah.bot.plugins.bmw_quotes. Skipping.')

    def test_missing_rooms_config(self):
        logging.warning = MagicMock()

        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.bmw_quotes', {}),))
        hipchat.connect = lambda: True
        hipchat.load_plugins(hipchat.plugins)
        hipchat.run()

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
            'Missing rooms configuration for schedule job. '
            'sarah.bot.plugins.bmw_quotes. Skipping.')

    def test_add_schedule_job(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.bmw_quotes',
                                    {'rooms': ('123_homer@localhost',)}),))
        hipchat.connect = lambda: True
        hipchat.run()

        jobs = hipchat.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'sarah.bot.plugins.bmw_quotes.bmw_quotes'
        assert isinstance(jobs[0].trigger, IntervalTrigger) is True
        assert jobs[0].trigger.interval_length == 300
        assert isinstance(jobs[0].func, types.FunctionType) is True


class TestCommandMessage(object):
    def test_init(self):
        msg = CommandMessage(original_text='.count foo',
                             text='foo',
                             sender='123_homer@localhost/Oklahomer')
        assert msg.original_text == '.count foo'
        assert msg.text == 'foo'
        assert msg.sender == '123_homer@localhost/Oklahomer'

        # Can't change
        msg.__original_text = 'foo'
        assert msg.original_text == '.count foo'
