# -*- coding: utf-8 -*-
# https://api.slack.com/rtm
from concurrent.futures import Future
import json
import logging
import re
from typing import Optional, Dict, Sequence
import requests
from websocket import WebSocketApp
from sarah.bot_base import BotBase, Command, concurrent
from sarah.types import PluginConfig


class CommandMessage:
    def __init__(self, original_text: str, text: str, sender: str):
        self.__original_text = original_text
        self.__text = text
        self.__sender = sender

    @property
    def original_text(self):
        return self.__original_text

    @property
    def text(self):
        return self.__text

    @property
    def sender(self):
        return self.__sender


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


class Slack(BotBase):
    CommandMessage = CommandMessage

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
        response = self.client.get('rtm.start')
        self.ws = WebSocketApp(response['url'],
                               on_message=self.message,
                               on_error=self.on_error,
                               on_open=self.on_open,
                               on_close=self.on_close)
        self.ws.run_forever()

    def add_schedule_job(self, command: Command) -> None:
        if 'channels' not in command.config:
            logging.warning(
                'Missing channel configuration for schedule job. %s. '
                'Skipping.' % command.module_name)
            return

        def job_function() -> None:
            ret = command.execute()
            for channel in command.config['channels']:
                self.enqueue_sending_message(self.send_message,
                                             channel,
                                             ret)

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

        command = self.find_command(content['text'])
        if command is None:
            return

        text = re.sub(r'{0}\s+'.format(command.name), '', content['text'])
        try:
            ret = command.execute(CommandMessage(original_text=content['text'],
                                                 text=text,
                                                 sender=content['user']))
        except Exception as e:
            logging.error('Error occurred. '
                          'command: %s. input: %s. error: %s.' % (
                              command.name, content['text'], e
                          ))
            return self.enqueue_sending_message(
                self.send_message,
                content['channel']
                ('Something went wrong with "%s"' % content['text']))
        else:
            return self.enqueue_sending_message(
                self.send_message,
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
