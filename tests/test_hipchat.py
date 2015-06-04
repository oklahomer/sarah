# -*- coding: utf-8 -*-
import pytest
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

    @pytest.fixture(scope='function')
    def hipchat(self, request):
        h = HipChat({'nick': 'Sarah',
                     'plugins': (('sarah.plugins.simple_counter', {}),
                                 ('sarah.plugins.echo', {}))})
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
