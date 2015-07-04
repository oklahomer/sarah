# -*- coding: utf-8 -*-

import logging
import numbers
import re
from sleekxmpp import ClientXMPP
from sleekxmpp.exceptions import IqTimeout, IqError
from sarah.bot_base import BotBase


class HipChat(BotBase):
    def __init__(self, config):
        super().__init__(config)
        self.client = self.setup_xmpp_client()
        self.scheduler = self.setup_scheduler()
        self.load_plugins(self.config.get('plugins', []))

    def run(self):
        if not self.client.connect():
            raise SarahHipChatException('Couldn\'t connect to server.')
        self.add_schedule_jobs(self.schedules)
        self.scheduler.start()
        self.client.process(block=True)

    def setup_xmpp_client(self):
        client = ClientXMPP(self.config['jid'], self.config['password'])

        if 'proxy' in self.config:
            client.use_proxy = True
            for key in ('host', 'port', 'username', 'password'):
                client.proxy_config[key] = self.config['proxy'].get(key, None)

        # TODO check later
        # client.add_event_handler('ssl_invalid_cert', lambda cert: True)

        client.add_event_handler('roster_update', self.join_rooms)
        client.add_event_handler('session_start', self.session_start)
        client.add_event_handler('message', self.message)
        client.register_plugin('xep_0045')
        client.register_plugin('xep_0203')

        return client

    def session_start(self, event):
        self.client.send_presence()

        # http://sleekxmpp.readthedocs.org/en/latest/getting_started/echobot.html
        # It is possible for a timeout to occur while waiting for the server to
        # respond, which can happen if the network is excessively slow or the
        # server is no longer responding. In that case, an IqTimeout is raised.
        # Similarly, an IqError exception can be raised if the request
        # contained
        # bad data or requested the roster for the wrong user.
        try:
            self.client.get_roster()
        except IqTimeout as e:
            raise SarahHipChatException(
                'Timeout occurred while getting roster. '
                'Error type: %s. Condition: %s.' % (
                    e.etype, e.condition))
        except IqError as e:
            # ret['type'] == 'error'
            raise SarahHipChatException(
                'IQError while getting roster. '
                'Error type: %s. Condition: %s. Content: %s.' % (
                    e.etype, e.condition, e.text))
        except Exception as e:
            raise SarahHipChatException('Unknown error occurred: %s.' % e)

    def join_rooms(self, event):
        # You MUST explicitly join rooms to receive message via XMPP interface
        for room in self.config.get('rooms', []):
            self.client.plugin['xep_0045'].joinMUC(room,
                                                   self.config.get('nick', ''),
                                                   maxhistory=None,
                                                   wait=True)

    def message(self, msg):
        if msg['delay']['stamp']:
            # Avoid answering to all past messages when joining the room.
            # xep_0203 plugin required.
            # http://xmpp.org/extensions/xep-0203.html
            #
            # FYI: When resource part of bot JabberID is 'bot' such as
            # 12_34@chat.example.com/bot, HipChat won't send us past messages
            return

        if msg['type'] in ('normal', 'chat'):
            # msg.reply("Thanks for sending\n%(body)s" % msg).send()
            pass

        elif msg['type'] == 'groupchat':
            # Don't talk to yourself. It's freaking people out.
            group_plugin = self.client.plugin['xep_0045']
            my_nick = group_plugin.ourNicks[msg.get_mucroom()]
            sender_nick = msg.get_mucnick()
            if my_nick == sender_nick:
                return

        command = self.find_command(msg['body'])
        if command is None:
            return

        text = re.sub(r'{0}\s+'.format(command['name']), '', msg['body'])
        ret = command['function']({'original_text': msg['body'],
                                   'text': text,
                                   'from': msg['from']},
                                  command['config'])
        if isinstance(ret, str):
            msg.reply(ret).send()
        elif isinstance(ret, numbers.Integral):
            msg.reply(str(ret)).send()
        else:
            logging.error('Malformed returning value. '
                          'Command: %s. Value: %s.' %
                          (command[1], str(ret)))

    def stop(self):
        logging.info('STOP SCHEDULER')
        if self.scheduler.running:
            self.scheduler.shutdown()
            logging.info('CANCELLED SCHEDULED WORK')

        logging.info('STOP HIPCHAT INTEGRATION')
        if hasattr(self, 'client') and self.client is not None:
            self.client.socket.recv_data(self.client.stream_footer)
            self.client.disconnect()
            logging.info('DISCONNECTED FROM HIPCHAT SERVER')


class SarahHipChatException(Exception):
    pass
