# -*- coding: utf-8 -*-
from typing import Dict

from sarah.hipchat import HipChat

__stash = {}


# noinspection PyUnusedLocal
@HipChat.command('.count')
def count(msg: HipChat.CommandMessage, config: Dict) -> str:
    if msg.sender not in __stash:
        __stash[msg.sender] = {}

    cnt = __stash[msg.sender].get(msg.text, 0) + 1
    __stash[msg.sender][msg.text] = cnt

    return str(cnt)


# noinspection PyUnusedLocal
@HipChat.command('.reset_count')
def reset_count(msg: HipChat.CommandMessage, config: Dict) -> str:
    global __stash
    __stash = {}
    return 'restart counting'
