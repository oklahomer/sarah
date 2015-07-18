# -*- coding: utf-8 -*-
from typing import Dict

from sarah.hipchat import HipChat

__stash = {}


# noinspection PyUnusedLocal
@HipChat.command('.count')
def count(msg: Dict, config: Dict) -> str:
    if not msg['from'] in __stash:
        __stash[msg['from']] = {}

    cnt = __stash[msg['from']].get(msg['text'], 0) + 1
    __stash[msg['from']][msg['text']] = cnt

    return str(cnt)


# noinspection PyUnusedLocal
@HipChat.command('.reset_count')
def reset_count(msg: Dict, config: Dict) -> str:
    global __stash
    __stash = {}
    return 'restart counting'
