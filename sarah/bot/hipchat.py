# -*- coding: utf-8 -*-
"""Provide HipChat interaction."""
import logging
from concurrent.futures import Future  # type: ignore
from sleekxmpp import ClientXMPP, Message  # type: ignore
from sleekxmpp.exceptions import IqTimeout, IqError  # type: ignore
from typing import Dict, Optional, Callable, Iterable
from sarah.bot import Base, concurrent
from sarah.bot.values import ScheduledCommand, PluginConfig
from sarah.exceptions import SarahException


class HipChat(Base):
    """Provide bot for HipChat."""

    def __init__(self,
                 plugins: Iterable[PluginConfig] = None,
                 jid: str = '',
                 password: str = '',
                 rooms: Iterable[str] = None,
                 nick: str = '',
                 proxy: Dict = None,
                 max_workers: int = None) -> None:
        """Initializer.

        :param plugins: List of plugin modules.
        :param jid: JID provided by HipChat.
        :param password: Password provided by HipChat.
        :param rooms: Rooms to join.
        :param nick: nickname to use.
        :param proxy: Proxy setting as dictionary.
        :param max_workers: Optional number of worker threads.
        :return: None
        """
        super().__init__(plugins=plugins, max_workers=max_workers)

        self.rooms = rooms if rooms else []  # type: Iterable[str]
        self.nick = nick
        self.client = self.setup_xmpp_client(jid, password, proxy)

    def generate_schedule_job(self,
                              command: ScheduledCommand) \
            -> Optional[Callable[..., None]]:
        """Generate callback function to be registered to scheduler.

        This creates a function that execute given command, handle the command
        response, and then submit response to message sending worker.

        :param command: ScheduledCommand object that holds job information
        :return: Optional callable object to be scheduled
        """
        # pop room configuration to leave minimal information for command
        # argument
        rooms = command.schedule_config.pop('rooms', [])
        if not rooms:
            logging.warning(
                'Missing rooms configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return None

        def job_function() -> None:
            ret = command()
            for room in rooms:
                self.enqueue_sending_message(
                    self.client.send_message,
                    mto=room,
                    mbody=ret,
                    mtype=command.schedule_config.get('message_type',
                                                      'groupchat'))

        return job_function

    def connect(self) -> None:
        """Connect to HipChat server and start interaction.

        :return: None
        """
        if not self.client.connect():
            raise SarahHipChatException("Couldn't connect to server.")
        self.client.process(block=True)

    def setup_xmpp_client(self,
                          jid: str,
                          password: str,
                          proxy: Dict = None) -> ClientXMPP:
        """Setup XMPP client and return its instance.

        :param jid: JID provided by HipChat.
        :param password: Password provided by HipChat.
        :param proxy: Proxy setting in dictionary.
        :return: ClientXMPP instance
        """
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
        """Callback method called by ClientXMPP on connection establishment.

        This explicitly sends Presence stanza to HipChat server, otherwise
        HipChat will not sends room messages to us.

        :param _: Dictionary that represent event.
        :return: None
        """
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
        """Join rooms.

        :param _: Dictionary that represent given event.
        :return: None
        """
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
        """Handle received message and submit the result to message worker.

        :param msg: Received message.
        :return: Optional Future instance that represent message sending
            result.
        """
        if msg['delay']['stamp']:
            # Avoid answering to all past messages when joining the room.
            # xep_0203 plugin required.
            # http://xmpp.org/extensions/xep-0203.html
            #
            # FYI: When resource part of bot JabberID is 'bot' such as
            # 12_34@chat.example.com/bot, HipChat won't send us past messages
            return None

        if msg['type'] in ('normal', 'chat'):
            # msg.reply("Thanks for sending\n%(body)s" % msg).send()
            pass

        elif msg['type'] == 'groupchat':
            # Don't talk to yourself. It's freaking people out.
            group_plugin = self.client.plugin['xep_0045']
            my_nick = group_plugin.ourNicks[msg.get_mucroom()]
            sender_nick = msg.get_mucnick()
            if my_nick == sender_nick:
                return None

        ret = self.respond(msg['from'], msg['body'])
        if ret:
            return self.enqueue_sending_message(lambda: msg.reply(ret).send())


class SarahHipChatException(SarahException):
    pass
