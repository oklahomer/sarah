# -*- coding: utf-8 -*-

import logging
import os
import sys
from configobj import ConfigObj
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqTimeout, IqError

class HipChat(object):
    def __init__(self, **kwargs):
        self.config = kwargs

        self.client = self.setup_xmpp_client()
        connected = self.client.connect()
        if not connected:
            raise SarahHipChatException('Coudn\'t connect to server.')

        self.client.process(block=True)

    def setup_xmpp_client(self):
        client = ClientXMPP(self.config['jid'], self.config['password'])

        if 'proxy_setting' in self.config:
            client.use_proxy = True
            client.proxy_config = {}
            for key in ('host', 'port', 'username', 'password'):
                client.proxy_config[key] = self.config.get(key, None)

        #TODO check later
        #client.add_event_handler('ssl_invalid_cert', lambda cert: True)

        client.add_event_handler('roster_update', self.join_rooms   )
        client.add_event_handler('session_start', self.session_start)
        client.add_event_handler('message'      , self.message      )
        client.register_plugin('xep_0045')
        client.register_plugin('xep_0203')

        return client

    def session_start(self, event):
        presence_ret = self.client.send_presence()

        # http://sleekxmpp.readthedocs.org/en/latest/getting_started/echobot.html
        # It is possible for a timeout to occur while waiting for the server to
        # respond, which can happen if the network is excessively slow or the
        # server is no longer responding. In that case, an IqTimeout is raised.
        # Similarly, an IqError exception can be raised if the request contained
        # bad data or requested the roster for the wrong user.
        try:
            self.client.get_roster()
        except IqTimeout as e:
            raise SarahHipChatException(
                    'Timeout occured while getting roster. '
                    'Error type: %s. Condition: %s.' %
                    e.etype, e.condition,
                  )
        except IqError as e:
            # ret['type'] == 'error'
            raise SarahHipChatException(
                    'Timeout occured while getting roster. '
                    'Error type: %s. Condition: %s. Content: %s.' %
                    e.etype, e.condition, e.text,
                  )
        except:
            raise SarahHipChatException('Unknown error occured.')

    def join_rooms(self, event):
        if 'rooms' not in self.config:
            return

        # You MUST explicitely join rooms to receive message via XMPP interface
        for room in self.config['rooms']:
            self.client.plugin['xep_0045'].joinMUC(room,
                                                   self.config.get('nick', ''),
                                                   maxhistory=None,
                                                   wait=True)

    def message(self, msg):
        if msg['delay']['stamp']:
            # Avoid answering to all past messages when joining the room.
            # xep_0203 plugin required.
            # http://xmpp.org/extensions/xep-0203.html
            return

        if msg['type'] in ('normal', 'chat'):
            msg.reply("Thanks for sending\n%(body)s" % msg).send()

        elif msg['type'] == 'groupchat':
            # Don't talk to yourself. It's freaking people out.
            my_nick = self.client.plugin['xep_0045'].ourNicks[msg.get_mucroom()]
            sender_nick = msg.get_mucnick()
            if my_nick == sender_nick:
                return

            msg.reply('Thanks. %(body)s' % msg).send()

class SarahHipChatException(Exception):
    pass

