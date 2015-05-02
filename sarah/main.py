# -*- coding: utf-8 -*-

import logging
import os
import sys
from configobj import ConfigObj
from sarah.hipchat import HipChat


class Sarah(object):
    def __init__(self, **kwargs):

        self.config = self.load_config(kwargs.get('config_paths', []))

    def start(self):
        if 'hipchat' in self.config:
            logging.info('Start HipChat integration')
            hipchat = HipChat(self)
            hipchat.start()

#        if 'irc' in self.config:
#            logging.info('Start IRC integration')
#            irc = IRC(**self.config.get('irc', {}))
#            irc.start()

    def load_config(self, paths):
        config = {}
        file_paths = [os.path.join(os.path.dirname(__file__), 'default.conf')]
        file_paths.extend(paths)

        for path in file_paths:
            try:
                config.update(ConfigObj(path))
            except:
                sys.stderr.write('Error while loading configuration file: %s' %
                                 path)

        return config


class SarahException(Exception):
    pass
