# -*- coding: utf-8 -*-

import random

from typing import Dict
from sarah.bot.values import CommandMessage
from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack, SlackMessage, MessageAttachment


# http://www.imdb.com/title/tt0105958/quotes
quotes = ([('Eric', "So i said to myself, 'Kyle'"),
           ('Alan', "Kyle?"),
           ('Eric', "That's what I call myself.")],
          [('Cory', "It's hard to imagine you as a boy.\n"
                    "Did your parents call you Mr. Feeny?")],
          ["[Jack and Eric are dressed up as girls to avoid bullies]",
           ('Feeny', "Hmm, double d's, just like your grades.")],
          [('Morgan', "Mommy, if my dolly's cold, "
                      "Can I put her in the toaster oven?"),
           ('Amy', "No, honey. That would be a mistake."),
           ('Morgan', "Mommy?"),
           ('Amy', "Yes?"),
           ('Morgan', "I made a mistake.")],
          [('Amy', "Apparently, Cory would rather listen to the "
                   "game than try and understand the emotional "
                   "content of Romeo & Juliet."),
           ('Cory', "Mom, I'm a kid. I don't understand the emotional content"
                    "of Full House."),
           ('Morgan', "I do.")],
          [('Topanga', "Cory, the worst thing that ever happened when we were "
                       "kids was that your Pop-Tart fell on the ground."),
           ('Cory', "Yeah, and *you* convinced me to eat it. You said, "
                    "\"God made dirt, dirt won't hurt.\"")])


def _hipchat_message():
    return "\n".join([q if isinstance(q, str) else
                      "%s: %s" % (q[0], q[1]) for q in random.choice(quotes)])


# noinspection PyUnusedLocal
@HipChat.command('.bmw')
def hipchat_quote(msg: CommandMessage, config: Dict) -> str:
    return _hipchat_message()


# noinspection PyUnusedLocal
@HipChat.schedule('bmw_quotes')
def hipchat_scheduled_quote(config: Dict) -> str:
    return _hipchat_message()


def _slack_message():
    quote = random.choice(quotes)
    if isinstance(quote[0], str):
        title = quote.pop(0)
    else:
        title = None

    color_map = {'Eric': "danger",
                 'Amy': "warning",
                 'Alan': "green",
                 'Cory': "green",
                 'Topanga': "warning",
                 'Morgan': "danger",
                 'Feeny': "danger"}
    return SlackMessage(
        text=title,
        attachments=[
            MessageAttachment(
                fallback="%s : %s" % (q[0], q[1]),
                pretext=q[0],
                title=q[1],
                color=color_map.get(q[0], "green")
            ) for q in quote])


# noinspection PyUnusedLocal
@Slack.command('.bmw')
def slack_quote(msg: CommandMessage, config: Dict) -> SlackMessage:
    return _slack_message()


# noinspection PyUnusedLocal
@Slack.schedule('bmw_quotes')
def slack_scheduled_quote(config: Dict) -> SlackMessage:
    return _slack_message()
