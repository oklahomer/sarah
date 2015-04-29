# -*- coding: utf-8 -*-

import re
from sarah.hipchat_decorator import hipchat_command
from sarah.hipchat_plugin import PluginBase

class EchoPlugin(PluginBase):
    @hipchat_command('.echo')
    def echo(self, msg):
        content = msg['body']
        content = re.sub(r'\.echo\s+', '', content)
        msg.reply(content).send()
