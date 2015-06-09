# -*- coding: utf-8 -*-
import pytest
import logging
from apscheduler.triggers.interval import IntervalTrigger
from sleekxmpp import ClientXMPP
from sleekxmpp.test import TestSocket
from sleekxmpp.stanza import Message
from mock import MagicMock, call
from sarah.hipchat import HipChat
import sarah.plugins.simple_counter
import types


def create_xmpp(self):
    # see sleekxmpp.test.sleektest for more
    xmpp = ClientXMPP('test@localhost', 'password', sasl_mech=None)
    xmpp._id_prefix = ''
    xmpp._disconnect_wait_for_threads = False
    xmpp.default_lang = None
    xmpp.peer_default_lang = None
    xmpp.set_socket(TestSocket())
    xmpp.auto_reconnect = False
    xmpp.state._set_state('connect')
    xmpp.socket.recv_data(xmpp.stream_header)

    xmpp.add_event_handler('roster_update', self.join_rooms)
    xmpp.add_event_handler('session_start', self.session_start)
    xmpp.add_event_handler('message', self.message)
    xmpp.register_plugin('xep_0045')
    xmpp.register_plugin('xep_0203')

    xmpp.use_message_ids = False
    return xmpp

HipChat.setup_xmpp_client = create_xmpp


class TestInit(object):
    def test_init(self):
        hipchat = HipChat({'nick': 'Sarah',
                           'plugins': (('sarah.plugins.simple_counter', {}),
                                       ('sarah.plugins.echo', {}))})

        assert isinstance(hipchat, HipChat) is True
        assert isinstance(hipchat.client, ClientXMPP) is True

        assert hipchat.commands[0][0] == '.count'
        assert hipchat.commands[0][2] == 'sarah.plugins.simple_counter'
        assert isinstance(hipchat.commands[1][1], types.FunctionType) is True

        assert hipchat.commands[1][0] == '.echo'
        assert isinstance(hipchat.commands[1][1], types.FunctionType) is True
        assert hipchat.commands[1][2] == 'sarah.plugins.echo'


class TestFindCommand(object):
    @pytest.fixture
    def hipchat(self, request):
        # NO h.start() for this test
        h = HipChat({'nick': 'Sarah',
                     'plugins': (
                         ('sarah.plugins.simple_counter', {'spam': 'ham'}),
                         ('sarah.plugins.echo', ))})
        return h

    def test_no_corresponding_command(self, hipchat):
        command = hipchat.find_command('egg')
        assert command is None

    def test_echo(self, hipchat):
        command = hipchat.find_command('.echo spam ham')
        assert command['config'] == {}
        assert command['name'] == '.echo'
        assert command['module_name'] == 'sarah.plugins.echo'
        assert isinstance(command['function'], types.FunctionType) is True

    def test_count(self, hipchat):
        command = hipchat.find_command('.count spam')
        assert command['config'] == {'spam': 'ham'}
        assert command['name'] == '.count'
        assert command['module_name'] == 'sarah.plugins.simple_counter'
        assert isinstance(command['function'], types.FunctionType) is True


class TestMessage(object):
    @pytest.fixture(scope='function')
    def hipchat(self, request):
        h = HipChat({'nick': 'Sarah',
                     'plugins': (('sarah.plugins.simple_counter', {}),
                                 ('sarah.plugins.echo',))})
        h.setDaemon(True)
        h.start()

        request.addfinalizer(h.stop)

        return h

    def test_skip_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = 'test body'

        msg.reply = MagicMock()

        hipchat.message(msg)
        assert msg.reply.call_count == 0

    def test_echo_message(self, hipchat):
        msg = Message(hipchat.client, stype='normal')
        msg['body'] = '.echo spam'

        msg.reply = MagicMock()

        hipchat.message(msg)
        assert msg.reply.call_count == 1
        assert msg.reply.call_args == call('spam')

    def test_count_message(self, hipchat):
        msg = Message(hipchat.client,
                      stype='normal',
                      sfrom='123_homer@localhost/Oklahomer')
        msg['body'] = '.count ham'

        msg.reply = MagicMock()

        hipchat.message(msg)
        assert msg.reply.call_count == 1
        assert msg.reply.call_args == call('1')

        hipchat.message(msg)
        assert msg.reply.call_count == 2
        assert msg.reply.call_args == call('2')

        msg['body'] = '.count egg'
        hipchat.message(msg)
        assert msg.reply.call_count == 3
        assert msg.reply.call_args == call('1')

        stash = vars(sarah.plugins.simple_counter).get('__stash', {})
        assert stash == {'123_homer@localhost/Oklahomer': {'ham': 2, 'egg': 1}}


class TestSchedule(object):
    @pytest.fixture
    def hipchat(self, request):
        # NO h.start() for this test
        h = HipChat({'nick': 'Sarah',
                     'plugins': (
                         ('sarah.plugins.bmw_quotes', {
                             'rooms': ('123_homer@localhost', ),
                             'interval': 5}))})
        return h

    def test_missing_config(self):
        logging.warning = MagicMock()

        h = HipChat({'nick': 'Sarah',
                     'plugins': (('sarah.plugins.bmw_quotes', ), )})
        h.add_schedule_jobs(h.schedules)

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
                'Missing configuration for schedule job. '
                'sarah.plugins.bmw_quotes. Skipping.')

    def test_missing_rooms_config(self):
        logging.warning = MagicMock()

        h = HipChat({'nick': 'Sarah',
                     'plugins': (('sarah.plugins.bmw_quotes', {}), )})
        h.add_schedule_jobs(h.schedules)

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
                'Missing rooms configuration for schedule job. '
                'sarah.plugins.bmw_quotes. Skipping.')

    def test_add_schedule_job(self):
        hipchat = HipChat({
            'nick': 'Sarah',
            'plugins': (('sarah.plugins.bmw_quotes',
                         {'rooms': ('123_homer@localhost', )}), )})
        hipchat.add_schedule_jobs(hipchat.schedules)

        jobs = hipchat.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'sarah.plugins.bmw_quotes.bmw_quotes'
        assert isinstance(jobs[0].trigger, IntervalTrigger) is True
        assert jobs[0].trigger.interval_length == 300
        assert isinstance(jobs[0].func, types.FunctionType) is True
