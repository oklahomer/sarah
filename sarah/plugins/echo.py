# -*- coding: utf-8 -*-

import re
from sarah.hipchat.decorator import command
from sarah.hipchat.plugin import PluginBase


class EchoPlugin(PluginBase):
    @command('.echo')
    def echo(self, msg):
        content = msg['body']
        content = re.sub(r'\.echo\s+', '', content)
        msg.reply(content).send()
