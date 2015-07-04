# -*- coding: utf-8 -*-
# https://api.slack.com/rtm

import logging
import websocket
import requests
from requests.compat import json
from sarah.bot_base import BotBase


class Slack(BotBase):
    def __init__(self, config):
        super().__init__(config)
        self.setup_client()
        self.message_id = 0
        self.load_plugins(self.config.get('plugins', []))

    def setup_client(self):
        self.client = SlackClient(token=self.config.get('token', ''))

    def run(self):
        response = self.client.get('rtm.start')
        self.ws = websocket.WebSocketApp(response['url'],
                                         on_message=self.message,
                                         on_error=self.on_error,
                                         on_open=self.on_open,
                                         on_close=self.on_close)
        self.ws.run_forever()

    def message(self, ws, event):
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

    def handle_hello(self, content):
        logging.info('Successfully connected to the server.')

    def handle_message(self, content):
        required_props = ('type', 'channel', 'user', 'text', 'ts')
        missing_props = [p for p in required_props if p not in content]

        if missing_props:
            logging.error('Malformed event is given. Missing %s. %s' % (
                ', '.join(missing_props),
                content))
            return

        # TODO Check command and return results
        # Just returning the exact same text for now.
        self.send_message(channel=content['channel'], text=content['text'])

    def on_error(self, ws, error):
        logging.error(error)

    def on_open(self, ws):
        logging.info('connected')

    def on_close(self, ws):
        logging.info('closed')

    def send_message(self, **kwargs):
        missing_params = [p for p in ('channel', 'text') if p not in kwargs]
        if missing_params:
            logging.error('Missing parameters: %s. %s' % (
                ', '.join(missing_params),
                kwargs))

        params = {'channel': kwargs['channel'],
                  'text': kwargs['text'],
                  'type': kwargs.get('type', 'message'),
                  'id': self.next_message_id()}
        self.ws.send(json.dumps(params))

    def next_message_id(self):
        # https://api.slack.com/rtm#sending_messages
        # Every event should have a unique (for that connection) positive
        # integer ID. All replies to that message will include this ID.
        self.message_id += 1
        return self.message_id

    def stop():
        # TODO
        pass


class SlackClient(object):
    def __init__(self, **kwargs):
        self.base_url = kwargs.get('base_url', 'https://slack.com/api/')
        self.token = kwargs.get('token', None)

    def generate_endpoint(self, method):
        # https://api.slack.com/methods
        return self.base_url + method if self.base_url.endswith('/') else \
            self.base_url + '/' + method

    def get(self, method):
        return self.request('GET', method)

    def post(self, method, params=None, data=None):
        return self.request('POST', method, params, data)

    def request(self, http_method, method, params=None, data=None):
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
            # TODO
            print(e)

        # Avoid "can't use a string pattern on a bytes-like object"
        # j = json.loads(response.content)
        return json.loads(response.content.decode())
