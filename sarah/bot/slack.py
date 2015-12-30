# -*- coding: utf-8 -*-
# https://api.slack.com/rtm
"""Provide Slack interaction."""
import json
import logging
from concurrent.futures import Future  # type: ignore
import requests
import time
from typing import Optional, Dict, Callable, Iterable
from websocket import WebSocketApp  # type: ignore
from sarah import ValueObject
from sarah.bot import Base, concurrent
from sarah.bot.values import ScheduledCommand, RichMessage, PluginConfig
from sarah.exceptions import SarahException

try:
    from typing import Any, Union

    # Work-around to avoid pyflakes warning "imported but unused" regarding
    # mypy's comment-styled type hinting
    # http://www.laurivan.com/make-pyflakespylint-ignore-unused-imports/
    # http://stackoverflow.com/questions/5033727/how-do-i-get-pyflakes-to-ignore-a-statement/12121404#12121404
    assert Any
    assert Union
except AssertionError:
    pass


class SlackClient(object):
    """A client module that provides access to Slack web API."""

    def __init__(self,
                 token: str,
                 base_url: str = 'https://slack.com/api/') -> None:
        """Initializer.

        :param token: Access token to be passed to Slack endpoint.
        :param base_url: Optional Slack API base url.
        :return: None.
        """
        self.base_url = base_url
        self.token = token

    def generate_endpoint(self, method: str) -> str:
        """Provide Slack endpoint with the given API method.

        See https://api.slack.com/methods for all provided methods.

        :param method: Slack method.
        :return: Stringified URL.
        """
        # https://api.slack.com/methods
        return self.base_url + method if self.base_url.endswith('/') else \
            self.base_url + '/' + method

    def get(self, method) -> Dict:
        """Wrapper method to make HTTP GET request with given Slack API method.

        :param method: Slack API method.
        :return: Dictionary that contains response.
        """
        return self.request('GET', method)

    def post(self, method, params=None, data=None) -> Dict:
        """Wrapper method to make HTTP POST request with given Slack API method.

        :param data: Sending query parameter.
        :param params: Sending data.
        :param method: Slack API method.
        :return: Dictionary that contains response.
        """
        return self.request('POST', method, params, data)

    def request(self,
                http_method: str,
                method: str,
                params: Dict = None,
                data: Dict = None) -> Dict:
        """Make HTTP request and return response as dictionary.

        :param http_method: HTTP request method.
        :param method: Slack API method.
        :param params: Sending query parameter.
        :param data: Sending data.
        :return: Dictionary that contains response.
        """
        http_method = http_method.upper()
        endpoint = self.generate_endpoint(method)

        if not params:
            params = {}
        if self.token:
            params['token'] = self.token

        try:
            response = requests.request(http_method,
                                        endpoint,
                                        params=params,
                                        data=data)
        except Exception as e:
            logging.error(e)
            raise e

        # Avoid "can't use a string pattern on a bytes-like object"
        # j = json.loads(response.content)
        return json.loads(response.content.decode())


class AttachmentField(ValueObject):
    def __init__(self, title: str, value: str, short: bool = None) -> None:
        pass

    def to_dict(self):
        # Exclude empty fields
        params = dict()
        for param in self.keys():
            if self[param] is None:
                continue

            params[param] = self[param]

        return params


# https://api.slack.com/docs/attachments
class MessageAttachment(ValueObject):
    def __init__(self,
                 fallback: str,
                 title: str,
                 title_link: str = None,
                 author_name: str = None,
                 author_link: str = None,
                 author_icon: str = None,
                 fields: Iterable[AttachmentField] = None,
                 image_url: str = None,
                 thumb_url: str = None,
                 pretext: str = None,
                 color: str = None) -> None:
        pass

    def to_dict(self):
        # Exclude empty fields
        params = dict()
        for param in self.keys():
            if self[param] is None:
                continue

            params[param] = self[param]

        if 'fields' in params:
            params['fields'] = [f.to_dict() for f in params['fields']]

        return params


class SlackMessage(RichMessage):
    def __init__(self,
                 text: str = None,
                 as_user: bool = True,
                 username: str = None,
                 parse: str = "full",
                 link_names: int = 1,
                 unfurl_links: bool = True,
                 unfurl_media: bool = False,
                 icon_url: str = None,
                 icon_emoji: str = None,
                 attachments: Iterable[MessageAttachment] = None) -> None:
        pass

    def __str__(self) -> str:
        return self['text']

    def to_dict(self):
        # Exclude empty fields
        params = dict()
        for param in self.keys():
            if self[param] is None:
                continue

            params[param] = self[param]

        return params

    def to_request_params(self) -> Dict:
        params = self.to_dict()

        if 'attachments' in params:
            params['attachments'] = json.dumps(
                [a.to_dict() for a in params['attachments']])

        return params


EventTypeMap = Dict[str, Dict[str, Union[Callable[..., Optional[Any]], str]]]


class Slack(Base):
    """Provide bot for Slack."""

    def __init__(self,
                 token: str = '',
                 plugins: Iterable[PluginConfig] = None,
                 max_workers: int = None) -> None:
        """Initializer.

        :param token: Access token provided by Slack.
        :param plugins: List of plugin modules.
        :param max_workers: Optional number of worker threads.
        :return: None
        """
        super().__init__(plugins=plugins, max_workers=max_workers)

        self.client = self.setup_client(token=token)
        self.message_id = 0
        self.ws = None  # type: WebSocketApp
        self.connect_attempt_count = 0

    def setup_client(self, token: str) -> SlackClient:
        """Setup ClackClient and return its instance.

        :param token: Slack access token.
        :return: SlackClient instance
        """
        return SlackClient(token=token)

    def connect(self) -> None:
        """Connect to Slack websocket server and start interaction.

        :return: None
        """
        while self.running:
            if self.connect_attempt_count >= 10:
                logging.error("Attempted 10 times, but all failed. Quitting.")
                break

            try:
                self.connect_attempt_count += 1
                self.try_connect()
            except Exception as e:
                logging.error(e)

            time.sleep(self.connect_attempt_count)

    def try_connect(self) -> None:
        """Try establish connection with Slack websocket server."""
        try:
            response = self.client.get('rtm.start')
            if 'url' not in response:
                raise Exception("url is not in the response. %s" % response)
        except Exception as e:
            raise SarahSlackException(
                "Slack request error on /rtm.start. %s" % e)
        else:
            self.ws = WebSocketApp(response['url'],
                                   on_message=self.message,
                                   on_error=self.on_error,
                                   on_open=self.on_open,
                                   on_close=self.on_close)
            self.ws.run_forever()

    def generate_schedule_job(self,
                              command: ScheduledCommand) \
            -> Optional[Callable[..., None]]:
        """Generate callback function to be registered to scheduler.

        This creates a function that execute given command and then handle the
        command response. If the response is SlackMessage instance, it make
        HTTP POST request to Slack web API endpoint. If string is returned,
        then it submit it to the message sending worker.

        :param command: ScheduledCommand object that holds job information
        :return: Optional callable object to be scheduled
        """
        channels = command.schedule_config.pop('channels', [])
        if not channels:
            logging.warning(
                'Missing channels configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return None

        def job_function() -> None:
            ret = command()
            if isinstance(ret, SlackMessage):
                for channel in channels:
                    # TODO Error handling
                    data = {'channel': channel}
                    data.update(ret.to_request_params())
                    self.client.post('chat.postMessage', data=data)
            else:
                for channel in channels:
                    self.enqueue_sending_message(self.send_message,
                                                 channel,
                                                 str(ret))

        return job_function

    @concurrent
    def message(self, _: WebSocketApp, event: str) -> None:
        """Receive event from Slack and dispatch it to corresponding method.

        :param _: WebSocketApp instance. This is not to be used here.
        :param event: JSON string that contains event information.
        :return: None
        """
        decoded_event = json.loads(event)

        if 'ok' in decoded_event and 'reply_to' in decoded_event:
            # https://api.slack.com/rtm#sending_messages
            # Replies to messages sent by clients will always contain two
            # properties: a boolean ok indicating whether they succeeded and
            # an integer reply_to indicating which message they are in response
            # to.
            if decoded_event['ok'] is False:
                # Something went wrong with the previous message
                logging.error(
                    'Something went wrong with the previous message. '
                    'message_id: %s. error: %s' % (
                        decoded_event['reply_to'],
                        decoded_event.get('error', "")))
            return None

        # TODO organize
        type_map = {
            'hello': {
                'method': self.handle_hello,
                'description': "The client has successfully connected to the "
                               "server"},
            'message': {
                'method': self.handle_message,
                'description': "A message was sent to a channel"},
            'user_typing': {
                'description': "A channel member is typing a message"},
            'presence_change': {
                'description': "A team member's presence changed"},
            'team_migration_started': {
                'method': self.handle_team_migration,
                'description': "The team is being migrated between servers"}
        }  # type: EventTypeMap

        if 'type' not in decoded_event:
            # https://api.slack.com/rtm#events
            # Every event has a type property which describes the type of
            # event.
            logging.error("Given event doesn't have type property. %s" %
                          event)
            return None

        if decoded_event['type'] not in type_map:
            logging.error('Unknown type value is given. %s' % event)
            return None

        logging.debug(
            '%s: %s. %s' % (
                decoded_event['type'],
                type_map[decoded_event['type']].get('description',
                                                    'NO DESCRIPTION'),
                event))

        method = type_map[decoded_event['type']].get('method', None)
        if method:
            method(decoded_event)

        return None

    def handle_hello(self, _: Dict) -> None:
        """Handle hello event.

        This is called when connection is established.

        :param _: Dictionary that represent event. This is not used here.
        :return: None
        """
        self.connect_attempt_count = 0  # Reset retry count
        logging.info('Successfully connected to the server.')

    def handle_message(self, content: Dict) -> Optional[Future]:
        """Handle message event.

        :param content: Dictionary that represent event.
        :return: Optional Future instance that represent message sending
            result.
        """
        # content
        # {
        #     "type":"message",
        #     "channel":"C06TXXXX",
        #     "user":"U06TXXXXX",
        #     "text":".bmw",
        #     "ts":"1438477080.000004",
        #     "team":"T06TXXXXX"
        # }
        required_props = ('type', 'channel', 'user', 'text', 'ts')
        missing_props = [p for p in required_props if p not in content]

        if missing_props:
            logging.error('Malformed event is given. Missing %s. %s' % (
                ', '.join(missing_props),
                content))
            return None

        ret = self.respond(content['user'], content['text'])
        if isinstance(ret, SlackMessage):
            # TODO Error handling
            data = {'channel': content["channel"]}
            data.update(ret.to_request_params())
            self.client.post('chat.postMessage', data=data)
            return None
        elif isinstance(ret, str):
            return self.enqueue_sending_message(self.send_message,
                                                content['channel'],
                                                ret)

    def handle_team_migration(self, _: Dict) -> None:
        """Handle team_migration_started event.

        https://api.slack.com/events/team_migration_started
        "When clients recieve this event they can immediately start a
        reconnection process by calling rtm.start again."

        :param _: Dictionary that represent event.
        :return: None
        """
        logging.info("Team migration started.")

    def on_error(self, _: WebSocketApp, error: Exception) -> None:
        """Callback method called by WebSocketApp when error occurred.

        :param _: WebSocketApp instance that is not currently used.
        :param error: Exception instance
        :return: None
        """
        logging.error("error %s", error)

    def on_open(self, _: WebSocketApp) -> None:
        """Callback method called by WebSocketApp on connection establishment.

        :param _: WebSocketApp instance that is not currently used.
        :return: None
        """
        logging.info('connected')

    def on_close(self, _: WebSocketApp, code: int, reason: str) -> None:
        """Callback method called by WebSocketApp when connection is closed.

        :param _: WebSocketApp instance that is not currently used.
        :param code: Closing code described in RFC6455.
            https://tools.ietf.org/html/rfc6455#section-7.4
        :param reason: Closing reason.
        :return: None
        """
        logging.info('connection closed. code: %d. reason: %s', code, reason)

    def send_message(self,
                     channel: str,
                     text: str,
                     message_type: str = 'message') -> None:
        """Send message to Slack via websocket connection.

        :param channel: Target channel to send message.
        :param text: Sending text.
        :param message_type: Message type. Default is "message."
        :return: None
        """
        params = {'channel': channel,
                  'text': text,
                  'type': message_type,
                  'id': self.next_message_id()}
        self.ws.send(json.dumps(params))

    def next_message_id(self) -> int:
        """Return unique ID for sending message.

        https://api.slack.com/rtm#sending_messages
        Every event should have a unique (for that connection) positive
        integer ID. All replies to that message will include this ID.

        :return: Unique ID as int
        """
        self.message_id += 1
        return self.message_id

    def disconnect(self) -> None:
        """Disconnect from Slack websocket server

        :return: None
        """
        self.ws.close()


class SarahSlackException(SarahException):
    pass
