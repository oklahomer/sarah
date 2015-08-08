# -*- coding: utf-8 -*-
from typing import Dict
from sarah import CommandMessage

from sarah.hipchat import HipChat
from sarah.slack import Slack

__stash = {'hipchat': {},
           'slack': {}}


def count(bot_type: str, user_key: str, key: str) -> int:
    stash = __stash[bot_type]
    if user_key not in stash:
        stash[user_key] = {}

    cnt = stash[user_key].get(key, 0) + 1
    stash[user_key][key] = cnt
    return cnt


def reset_count(bot_type: str) -> None:
    stash = __stash[bot_type]
    stash.clear()


# noinspection PyUnusedLocal
@HipChat.command('.count')
def hipchat_count(msg: CommandMessage, config: Dict) -> str:
    return str(count('hipchat', msg.sender, msg.text))


# noinspection PyUnusedLocal
@HipChat.command('.reset_count')
def hipchat_reset_count(msg: CommandMessage, config: Dict) -> str:
    reset_count('hipchat')
    return 'restart counting'


# noinspection PyUnusedLocal
@Slack.command('.count')
def slack_count(msg: CommandMessage, config: Dict) -> str:
    return str(count('slack', msg.sender, msg.text))


# noinspection PyUnusedLocal
@Slack.command('.reset_count')
def slack_reset_count(msg: CommandMessage, config: Dict) -> str:
    reset_count('slack')
    return 'restart counting'
