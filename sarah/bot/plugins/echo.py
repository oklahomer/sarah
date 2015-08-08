# -*- coding: utf-8 -*-
from typing import Dict
from sarah.bot import CommandMessage

from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack


# noinspection PyUnusedLocal
@HipChat.command('.echo')
def hipchat_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text


# noinspection PyUnusedLocal
@Slack.command('.echo')
def slack_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text
