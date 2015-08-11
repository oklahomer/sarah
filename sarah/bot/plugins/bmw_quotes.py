# -*- coding: utf-8 -*-

import random

from typing import Dict
from sarah.bot.values import CommandMessage
from sarah.bot.hipchat import HipChat
from sarah.bot.slack import Slack


# http://www.imdb.com/title/tt0105958/quotes
quotes = (("Eric: So I said to myself, 'Kyle,'\n"
           "Alan: Kyle?\n"
           "Eric: That's what I call myself."),
          ("Cory: It's hard to imagine you as a boy. \n"
           "Did your parents call you Mr. Feeny?"),
          ("[Jack and Eric are dressed up as girls to avoid bullies]\n"
           "Mr. George Feeny: Hmm, double d's, just like your grades."),
          ("Morgan Matthews: Mommy, if my dolly's cold, "
           "can I put her in the toaster oven?\n"
           "Amy Matthews: No, honey. That would be a mistake.\n"
           "Morgan Matthews: Mommy?\n"
           "Amy Matthews: Yes?\n"
           "Morgan Matthews: I made a mistake."),
          ("Amy Matthews: Apparently, Cory would rather listen to the game "
           "then try and understand the emotional content of Romeo & Juliet.\n"
           "Cory: Mom, I'm a kid. I don't understand the emotional content "
           "of Full House.\n"
           "Morgan Matthews: I do."),
          ("Topanga: Cory, the worst thing that ever happened "
           "when we were kids was that your Pop-Tart fell on the ground.\n"
           "Cory: Yeah, and *you* convinced me to eat it. You said, "
           "\"God made dirt, dirt won't hurt.\""))


# noinspection PyUnusedLocal
@HipChat.command('.bmw')
def hipchat_quote(msg: CommandMessage, config: Dict) -> str:
    return random.choice(quotes)


# noinspection PyUnusedLocal
@HipChat.schedule('bmw_quotes')
def hipchat_scheduled_quote(config: Dict) -> str:
    return random.choice(quotes)


# noinspection PyUnusedLocal
@Slack.command('.bmw')
def slack_quote(msg: CommandMessage, config: Dict) -> str:
    return random.choice(quotes)


# noinspection PyUnusedLocal
@Slack.schedule('bmw_quotes')
def slack_scheduled_quote(config: Dict) -> str:
    return random.choice(quotes)
