# -*- coding: utf-8 -*-

from sarah.hipchat import HipChat


@HipChat.command('.echo')
def echo(msg):
    return msg['text']
