# -*- coding: utf-8 -*-

from sarah.hipchat import HipChat

__stash = {}


@HipChat.command('.count')
def count(msg):
    if not msg['from'] in __stash:
        __stash[msg['from']] = {}

    cnt = __stash[msg['from']].get(msg['text'], 0) + 1
    __stash[msg['from']][msg['text']] = cnt

    return cnt
