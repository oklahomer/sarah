# -*- coding: utf-8 -*-
# https://api.slack.com/rtm
from concurrent.futures import Future
import json
import logging

from typing import Optional, Dict, Sequence
import requests
from websocket import WebSocketApp
from sarah import ValueObject

from sarah.exceptions import SarahException
from sarah.bot import Base, concurrent
from sarah.bot.values import Command, RichMessage
from sarah.bot.types import PluginConfig


class SlackClient(object):
    def __init__(self,
                 token: str,
                 base_url: str='https://slack.com/api/') -> None:
        self.base_url = base_url
        self.token = token

    def generate_endpoint(self, method: str) -> str:
        # https://api.slack.com/methods
        return self.base_url + method if self.base_url.endswith('/') else \
            self.base_url + '/' + method

    def get(self, method) -> Dict:
        return self.request('GET', method)

    def post(self, method, params=None, data=None) -> Dict:
        return self.request('POST', method, params, data)

    def request(self,
                http_method: str,
                method: str,
                params: Dict=None,
                data: Dict=None) -> Dict:
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
    def __init__(self, title: str, value: str, short: bool=None):
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
                 title_link: str=None,
                 author_name: str=None,
                 author_link: str=None,
                 author_icon: str=None,
                 fields: Sequence[AttachmentField]=None,
                 image_url: str=None,
                 thumb_url: str=None,
                 pretext: str=None,
                 color: str=None):
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
                 text: str=None,
                 as_user: bool=True,
                 username: str=None,
                 parse: str="full",
                 link_names: int=1,
                 unfurl_links: bool=True,
                 unfurl_media: bool=False,
                 icon_url: str=None,
                 icon_emoji: str=None,
                 attachments: Sequence[MessageAttachment]=None):
        pass

    def to_dict(self):
        # Exclude empty fields
        params = dict()
        for param in self.keys():
            if self[param] is None:
                continue

            params[param] = self[param]

        return params

    def to_request_params(self):
        params = self.to_dict()

        if 'attachments' in params:
            params['attachments'] = json.dumps(
                [a.to_dict() for a in params['attachments']])

        return params


class Slack(Base):
    def __init__(self,
                 token: str='',
                 plugins: Sequence[PluginConfig]=None,
                 max_workers: int=None) -> None:

        super().__init__(plugins=plugins, max_workers=max_workers)

        self.client = self.setup_client(token=token)
        self.message_id = 0
        self.ws = None

    def setup_client(self, token: str) -> SlackClient:
        return SlackClient(token=token)

    def connect(self) -> None:
        try:
            response = self.client.get('rtm.start')
        except Exception as e:
            raise SarahSlackException(
                "Slack request error on /rtm.start. %s" % e)
        else:
            if 'url' not in response:
                raise SarahSlackException(
                    "Slack response did not contain connecting url. %s" %
                    response)

            self.ws = WebSocketApp(response['url'],
                                   on_message=self.message,
                                   on_error=self.on_error,
                                   on_open=self.on_open,
                                   on_close=self.on_close)
            self.ws.run_forever()

    def add_schedule_job(self, command: Command) -> None:
        if 'channels' not in command.config:
            logging.warning(
                'Missing channels configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return

        def job_function() -> None:
            ret = command.execute()
            if isinstance(ret, SlackMessage):
                for channel in command.config['channels']:
                    # TODO Error handling
                    data = dict({'channel': channel})
                    data.update(ret.to_request_params())
                    self.client.post('chat.postMessage', data=data)
            else:
                for channel in command.config['channels']:
                    self.enqueue_sending_message(self.send_message,
                                                 channel,
                                                 str(ret))

        job_id = '%s.%s' % (command.module_name, command.name)
        logging.info("Add schedule %s" % id)
        self.scheduler.add_job(
            job_function,
            'interval',
            id=job_id,
            minutes=command.config.get('interval', 5))

    @concurrent
    def message(self, _: WebSocketApp, event: str) -> None:
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
                    'message_id: %d. error: %s' % (decoded_event['reply_to'],
                                                   decoded_event['error']))
            return

        # TODO organize
        type_map = {
            'hello': {'method': self.handle_hello,
                      'description': 'The client has successfully connected '
                                     'to the server'},
            'message': {'method': self.handle_message,
                        'description': 'A message was sent to a channel'},
            'user_typing': {'description': 'A channel member is typing a '
                                           'message'}}

        if 'type' not in decoded_event:
            # https://api.slack.com/rtm#events
            # Every event has a type property which describes the type of
            # event.
            logging.error('Given event doesn\'t have type property. %s' %
                          event)
            return

        if decoded_event['type'] not in type_map:
            logging.error('Unknown type value is given. %s' % event)
            return

        logging.debug(
            '%s: %s. %s' % (
                decoded_event['type'],
                type_map[decoded_event['type']].get('description',
                                                    'NO DESCRIPTION'),
                event))

        if 'method' in type_map[decoded_event['type']]:
            type_map[decoded_event['type']]['method'](decoded_event)
            return

    def handle_hello(self, _: Dict) -> None:
        logging.info('Successfully connected to the server.')

    def handle_message(self, content: Dict) -> Optional[Future]:
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
            return

        ret = self.respond(content['user'], content['text'])
        if isinstance(ret, SlackMessage):
            # TODO Error handling
            data = dict({'channel': content["channel"]})
            data.update(ret.to_request_params())
            self.client.post('chat.postMessage', data=data)
        elif isinstance(ret, str):
            return self.enqueue_sending_message(self.send_message,
                                                content['channel'],
                                                ret)

    def on_error(self, _: WebSocketApp, error) -> None:
        logging.error(error)

    def on_open(self, _: WebSocketApp) -> None:
        logging.info('connected')

    def on_close(self, _: WebSocketApp) -> None:
        logging.info('closed')

    def send_message(self,
                     channel: str,
                     text: str,
                     message_type: str='message') -> None:
        params = {'channel': channel,
                  'text': text,
                  'type': message_type,
                  'id': self.next_message_id()}
        self.ws.send(json.dumps(params))

    def next_message_id(self) -> int:
        # https://api.slack.com/rtm#sending_messages
        # Every event should have a unique (for that connection) positive
        # integer ID. All replies to that message will include this ID.
        self.message_id += 1
        return self.message_id

    def stop(self) -> None:
        super().stop()
        logging.info('STOP SLACK INTEGRATION')
        self.ws.close()


class SarahSlackException(SarahException):
    pass
