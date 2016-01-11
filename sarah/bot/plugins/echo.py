# -*- coding: utf-8 -*-
from typing import Dict
from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack
from sarah.bot.gitter import Gitter
from sarah.bot.values import CommandMessage


# noinspection PyUnusedLocal
@HipChat.command('.echo')
def hipchat_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text


# noinspection PyUnusedLocal
@Slack.command('.echo')
def slack_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text


# noinspection PyUnusedLocal
@Gitter.command('.echo')
def gitter_echo(msg: CommandMessage, config: Dict) -> str:
    return msg.text
