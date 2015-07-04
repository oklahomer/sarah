# -*- coding: utf-8 -*-

import logging
import os
import yaml
from threading import Thread
from sarah.hipchat import HipChat
from sarah.slack import Slack


class Sarah(object):
    def __init__(self, config_paths=[]):

        self.config = self.load_config(config_paths)

    def start(self):
        if 'hipchat' in self.config:
            logging.info('Start HipChat integration')
            hipchat = HipChat(self.config['hipchat'])
            hipchat_thread = Thread(target=hipchat.run)
            hipchat_thread.start()

        if 'slack' in self.config:
            logging.info('Start Slack integration')
            slack = Slack(self.config['slack'])
            slack_thread = Thread(target=slack.run)
            slack_thread.start()

    @staticmethod
    def load_config(paths):
        config = {}

        for path in paths:
            is_file = os.path.isfile(path)
            if is_file is False:
                raise SarahException('Configuration file does not exist. %s' %
                                     path)

            try:
                config.update(yaml.load(open(path, 'r')))
            except:
                raise SarahException('Can\'t load configuration file. %s' %
                                     path)

        return config


class SarahException(Exception):
    pass
