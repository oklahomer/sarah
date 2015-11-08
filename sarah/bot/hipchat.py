# -*- coding: utf-8 -*-
from concurrent.futures import Future
import logging

from sleekxmpp import ClientXMPP, Message
from sleekxmpp.exceptions import IqTimeout, IqError
from typing import Dict, Optional, Callable, Iterable
from sarah.exceptions import SarahException
from sarah.bot import Base, concurrent
from sarah.bot.values import ScheduledCommand
from sarah.bot.types import PluginConfig


class HipChat(Base):
    def __init__(self,
                 plugins: Iterable[PluginConfig]=None,
                 jid: str='',
                 password: str='',
                 rooms: Iterable[str]=None,
                 nick: str='',
                 proxy: Dict=None,
                 max_workers: int=None) -> None:

        super().__init__(plugins=plugins, max_workers=max_workers)

        self.rooms = rooms if rooms else []  # type: Iterable[str]
        self.nick = nick
        self.client = self.setup_xmpp_client(jid, password, proxy)

    def generate_schedule_job(self,
                              command: ScheduledCommand) -> Optional[Callable]:
        # pop room configuration to leave minimal information for command
        # argument
        rooms = command.schedule_config.pop('rooms', [])
        if not rooms:
            logging.warning(
                'Missing rooms configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return

        def job_function() -> None:
            ret = command.execute()
            for room in rooms:
                self.enqueue_sending_message(
                    self.client.send_message,
                    mto=room,
                    mbody=ret,
                    mtype=command.schedule_config.get('message_type',
                                                      'groupchat'))

        return job_function

    def connect(self) -> None:
        if not self.client.connect():
            raise SarahHipChatException("Couldn't connect to server.")
        self.client.process(block=True)

    def setup_xmpp_client(self,
                          jid: str,
                          password: str,
                          proxy: Dict=None) -> ClientXMPP:
        client = ClientXMPP(jid, password)

        if proxy:
            client.use_proxy = True
            for key in ('host', 'port', 'username', 'password'):
                client.proxy_config[key] = proxy.get(key, None)

        # TODO check later
        # client.add_event_handler('ssl_invalid_cert', lambda cert: True)

        client.add_event_handler('session_start', self.session_start)
        client.add_event_handler('roster_update', self.join_rooms)
        client.add_event_handler('message', self.message)
        client.register_plugin('xep_0045')
        client.register_plugin('xep_0203')

        return client

    def session_start(self, _: Dict) -> None:
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

    @concurrent
    def join_rooms(self, _: Dict) -> None:
        if not self.rooms:
            return

        # You MUST explicitly join rooms to receive message via XMPP
        # interface
        for room in self.rooms:
            self.client.plugin['xep_0045'].joinMUC(room,
                                                   self.nick,
                                                   maxhistory=None,
                                                   wait=True)

    @concurrent
    def message(self, msg: Message) -> Optional[Future]:
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

        ret = self.respond(msg['from'], msg['body'])
        if ret:
            return self.enqueue_sending_message(lambda: msg.reply(ret).send())

    def stop(self) -> None:
        super().stop()
        logging.info('STOP HIPCHAT INTEGRATION')
        if hasattr(self, 'client') and self.client is not None:
            self.client.socket.recv_data(self.client.stream_footer)
            self.client.disconnect()
            logging.info('DISCONNECTED FROM HIPCHAT SERVER')


class SarahHipChatException(SarahException):
    pass
