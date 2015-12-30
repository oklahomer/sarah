# -*- coding: utf-8 -*-
"""Sample script to run Bot with specified settings.

Give a path to a configuration yaml file or place a file named sarah.yaml in
the same directory.
"""
import logging
import os
from multiprocessing import Process  # type: ignore

import sys
import yaml  # type: ignore
from typing import Dict, Iterable
from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack
from sarah.exceptions import SarahException

try:
    from typing import Any

    # Work-around to avoid pyflakes warning "imported but unused" regarding
    # mypy's comment-styled type hinting
    # http://www.laurivan.com/make-pyflakespylint-ignore-unused-imports/
    # http://stackoverflow.com/questions/5033727/how-do-i-get-pyflakes-to-ignore-a-statement/12121404#12121404
    assert Any
except AssertionError:
    pass


class Sarah(object):
    def __init__(self,
                 config_paths: Iterable[str]) -> None:

        self.config = self.load_config(config_paths)

    def start(self) -> None:
        processes = []

        if 'hipchat' in self.config:
            logging.info('Start HipChat integration')
            hipchat = HipChat(**self.config['hipchat'])
            processes.append(Process(target=hipchat.run))

        if 'slack' in self.config:
            logging.info('Start Slack integration')
            slack = Slack(**self.config['slack'])
            processes.append(Process(target=slack.run))

        for process in processes:
            process.start()

    @staticmethod
    def load_config(paths: Iterable[str]) -> Dict:
        config = {}  # type: Dict[str, Any]

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

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-8s %(message)s')

    arguments = sys.argv

    config_path = arguments[1] if len(arguments) > 1 \
        else os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'sarah.yaml')

    sarah = Sarah(config_paths=[config_path])
    sarah.start()
