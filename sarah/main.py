# -*- coding: utf-8 -*-

import logging
import os
from multiprocessing import Process

import yaml
from typing import Dict, Sequence

from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack
from sarah.bot.types import Path
from sarah.exceptions import SarahException


class Sarah(object):
    def __init__(self,
                 config_paths: Sequence[Path]) -> None:

        self.config = self.load_config(config_paths)

    def start(self) -> None:
        if 'hipchat' in self.config:
            logging.info('Start HipChat integration')
            hipchat = HipChat(**self.config['hipchat'])
            hipchat_process = Process(target=hipchat.run)
            hipchat_process.start()

        if 'slack' in self.config:
            logging.info('Start Slack integration')
            slack = Slack(**self.config['slack'])
            slack_process = Process(target=slack.run)
            slack_process.start()

    @staticmethod
    def load_config(paths: Sequence[Path]) -> Dict:
        config = {}

        if not paths:
            return config

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
