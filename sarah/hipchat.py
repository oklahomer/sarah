# -*- coding: utf-8 -*-
import logging
import re
from sleekxmpp import ClientXMPP, Message
from sleekxmpp.exceptions import IqTimeout, IqError
from typing import Dict, List, Optional, Tuple, Union
from sarah.bot_base import BotBase, Command


class HipChat(BotBase):
    def __init__(self,
                 plugins: Optional[Union[List, Tuple]]=None,
                 jid: str='',
                 password: str='',
                 rooms: Optional[Union[List, Tuple]]=None,
                 nick: str='',
                 proxy: Optional[Dict]=None,
                 max_workers: Optional[int]=None) -> None:
        if not plugins:
            plugins = []
        if not rooms:
            rooms = []

        super().__init__(plugins=plugins, max_workers=max_workers)

        self.rooms = rooms
        self.nick = nick
        self.client = self.setup_xmpp_client(jid, password, proxy)

    def add_schedule_job(self, command: Command) -> None:
        if 'rooms' not in command.config:
            logging.warning(
                'Missing rooms configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return

        def job_function():
            ret = command.execute()
            for room in command.config['rooms']:
                self.client.send_message(
                    mto=room,
                    mbody=ret,
                    mtype=command.config.get('message_type', 'groupchat'))

        job_id = '%s.%s' % (command.module_name, command.name)
        logging.info("Add schedule %s" % id)
        self.scheduler.add_job(
            job_function,
            'interval',
            id=job_id,
            minutes=command.config.get('interval', 5))

    def run(self) -> None:
        if not self.client.connect():
            raise SarahHipChatException('Couldn\'t connect to server.')
        self.scheduler.start()
        self.client.process(block=True)

    def setup_xmpp_client(self,
                          jid: str,
                          password: str,
                          proxy: Optional[Dict]=None) -> ClientXMPP:
        client = ClientXMPP(jid, password)

        if proxy:
            client.use_proxy = True
            for key in ('host', 'port', 'username', 'password'):
                client.proxy_config[key] = proxy.get(key, None)

        # TODO check later
        # client.add_event_handler('ssl_invalid_cert', lambda cert: True)

        client.add_event_handler('session_start', self.session_start)
        client.add_event_handler('roster_update',
                                 self.add_queue(self.join_rooms))
        client.add_event_handler('message', self.add_queue(self.message))
        client.register_plugin('xep_0045')
        client.register_plugin('xep_0203')

        return client

    def session_start(self, event: Dict) -> None:
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

    def join_rooms(self, event: Dict) -> None:
        # You MUST explicitly join rooms to receive message via XMPP interface
        for room in self.rooms:
            self.client.plugin['xep_0045'].joinMUC(room,
                                                   self.nick,
                                                   maxhistory=None,
                                                   wait=True)

    def message(self, msg: Message) -> None:
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

        text = re.sub(r'{0}\s+'.format(command.name), '', msg['body'])
        try:
            ret = command.execute({'original_text': msg['body'],
                                   'text': text,
                                   'from': msg['from']})
        except Exception as e:
            msg.reply('Something went wrong with "%s"' % msg['body']).send()
            logging.error('Error occurred. '
                          'command: %s. input: %s. error: %s.' % (
                              command.name, msg['body'], e
                          ))
        else:
            msg.reply(ret).send()

    def stop(self) -> None:
        super().stop()
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
