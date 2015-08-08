# -*- coding: utf-8 -*-
from typing import Dict
from sarah import CommandMessage

from sarah.hipchat import HipChat
from sarah.slack import Slack


# noinspection PyUnusedLocal
@HipChat.command('.echo')
def hipchat_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text


# noinspection PyUnusedLocal
@Slack.command('.echo')
def slack_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text
