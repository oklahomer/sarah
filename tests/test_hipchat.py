# -*- coding: utf-8 -*-
import concurrent
from concurrent.futures import ALL_COMPLETED
from time import sleep
import logging
import types

import pytest
from sleekxmpp import ClientXMPP
from sleekxmpp.test import TestSocket
from sleekxmpp.stanza import Message
from sleekxmpp.exceptions import IqTimeout, IqError
from sleekxmpp.xmlstream import JID
from mock import MagicMock, call, patch

from sarah.bot.values import UserContext, CommandMessage, Command
from sarah.bot.hipchat import HipChat, SarahHipChatException
import sarah.bot.plugins.simple_counter
from assertpy import assert_that


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

        hipchat.load_plugins(hipchat.plugin_modules)

        assert_that(hipchat.commands).extract('name').contains('.count',
                                                               '.reset_count',
                                                               '.echo')

        assert_that(hipchat.commands) \
            .extract('name', 'module_name') \
            .contains_sequence(('.count', 'sarah.bot.plugins.simple_counter'),
                               ('.reset_count',
                                'sarah.bot.plugins.simple_counter'),
                               ('.echo', 'sarah.bot.plugins.echo'))

        for command in hipchat.commands:
            assert_that(command.function).is_type_of(types.FunctionType)

    def test_non_existing_plugin(self):
        h = HipChat(nick='Sarah',
                    jid='test@localhost',
                    password='password',
                    plugins=(('spam.ham.egg.onion', {}),))
        h.load_plugins(h.plugin_modules)

        assert_that(h.commands).is_empty()
        assert_that(h.scheduler.get_jobs()).is_empty()

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

                assert_that(mock_client_process.call_count).is_equal_to(1)
                assert_that(hipchat.scheduler.running).is_true()


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
        h.load_plugins(h.plugin_modules)
        return h

    def test_no_corresponding_command(self, hipchat):
        assert_that(hipchat.find_command('egg')).is_none()

    def test_echo(self, hipchat):
        assert_that(hipchat.find_command('.echo spam ham')) \
            .is_instance_of(Command) \
            .has_config({}) \
            .has_name('.echo') \
            .has_module_name('sarah.bot.plugins.echo')

    def test_count(self, hipchat):
        assert_that(hipchat.find_command('.count spam')) \
            .is_instance_of(Command) \
            .has_config({'spam': 'ham'}) \
            .has_name('.count') \
            .has_module_name('sarah.bot.plugins.simple_counter')


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
        assert_that(ret.done).contains(future)

    def test_skip_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = 'test body'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert_that(msg.reply.call_count).is_equal_to(0)

    def test_echo_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = '.echo spam'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert_that(msg.reply.call_count).is_equal_to(1)
        assert_that(msg.reply.call_args).is_equal_to(call('spam'))

    def test_count_message(self, hipchat):
        msg = Message(hipchat.client,
                      stype='normal',
                      sfrom='123_homer@localhost/Oklahomer')
        msg['body'] = '.count ham'

        msg.reply = MagicMock()

        self.wait_future_finish(hipchat.message(msg))
        assert_that(msg.reply.call_count).is_equal_to(1)
        assert_that(msg.reply.call_args).is_equal_to(call('1'))

        self.wait_future_finish(hipchat.message(msg))
        assert_that(msg.reply.call_count).is_equal_to(2)
        assert_that(msg.reply.call_args).is_equal_to(call('2'))

        msg['body'] = '.count egg'
        self.wait_future_finish(hipchat.message(msg))
        assert_that(msg.reply.call_count).is_equal_to(3)
        assert_that(msg.reply.call_args).is_equal_to(call('1'))

        stash = vars(sarah.bot.plugins.simple_counter) \
            .get('__stash') \
            .get('hipchat')
        assert_that(stash) \
            .is_equal_to({'123_homer@localhost/Oklahomer': {'ham': 2,
                                                            'egg': 1}})

    def test_conversation(self, hipchat):
        user_key = '123_homer@localhost/Oklahomer'

        # Initial message
        assert_that(hipchat.respond(user_key, '.hello')) \
            .is_equal_to("Hello. How are you feeling today?")

        # Context is set
        assert_that(hipchat.user_context_map.get(user_key)) \
            .is_instance_of(UserContext)

        # Wrong formatted message results with help message
        assert_that(hipchat.respond(user_key, "SomeBizarreText")) \
            .is_equal_to("Say Good or Bad, please.")

        assert_that(hipchat.respond(user_key, "Bad")) \
            .is_equal_to("Are you sick?")

        # Still in conversation
        assert_that(hipchat.user_context_map.get(user_key)) \
            .is_instance_of(UserContext)

        # The last yes/no question
        assert_that(hipchat.respond(user_key, "Yes")) \
            .is_equal_to("I'm sorry to hear that. Hope you get better, soon.")

        # Context is removed
        assert_that(hipchat.user_context_map.get(user_key)).is_none()


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

        assert_that(hipchat.scheduler.get_jobs()) \
            .described_as("No module is loaded") \
            .is_empty()
        assert_that(logging.warning.call_count).is_equal_to(1)
        assert_that(logging.warning.call_args) \
            .is_equal_to(call('Missing configuration for schedule job. '
                              'sarah.bot.plugins.bmw_quotes. Skipping.'))

    def test_missing_rooms_config(self):
        logging.warning = MagicMock()

        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.bmw_quotes', {}),))
        hipchat.connect = lambda: True
        hipchat.load_plugins(hipchat.plugin_modules)
        hipchat.run()

        assert_that(logging.warning.call_count).is_true()
        assert_that(logging.warning.call_args) \
            .is_equal_to(call('Missing rooms configuration for schedule job. '
                              'sarah.bot.plugins.bmw_quotes. Skipping.'))

    def test_add_schedule_job(self):
        hipchat = HipChat(nick='Sarah',
                          jid='test@localhost',
                          password='password',
                          plugins=(('sarah.bot.plugins.bmw_quotes',
                                    {'rooms': ('123_homer@localhost',)}),))
        hipchat.connect = lambda: True
        hipchat.run()

        jobs = hipchat.scheduler.get_jobs()
        assert_that(jobs).is_length(1)
        assert_that(jobs[0]).has_id('sarah.bot.plugins.bmw_quotes.bmw_quotes')
        assert_that(jobs[0].trigger).has_interval_length(300)


class TestCommandMessage(object):
    def test_init(self):
        msg = CommandMessage(original_text='.count foo',
                             text='foo',
                             sender='123_homer@localhost/Oklahomer')
        assert_that(msg) \
            .has_original_text('.count foo') \
            .has_text('foo') \
            .has_sender('123_homer@localhost/Oklahomer')

        # Can't change
        msg.__original_text = 'foo'
        assert_that(msg).has_original_text('.count foo')
