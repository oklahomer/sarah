# -*- coding: utf-8 -*-
from typing import Dict

from sarah.hipchat import HipChat


# noinspection PyUnusedLocal
@HipChat.command('.echo')
def echo(msg: HipChat.CommandMessage, config: Dict) -> str:
    return msg.text
