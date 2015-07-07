# -*- coding: utf-8 -*-
from typing import Dict

from sarah.hipchat import HipChat


@HipChat.command('.echo')
def echo(msg: Dict, config: Dict) -> str:
    return msg['text']
