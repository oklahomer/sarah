# -*- coding: utf-8 -*-
from typing import Dict
from sarah import UserContext, InputOption, CommandMessage
from sarah.hipchat import HipChat


# noinspection PyUnusedLocal
@HipChat.command('.hello')
def hipchat_hello(msg: CommandMessage, config: Dict) -> UserContext:
    # Return UserContext to start conversation. State will be stored for later
    # user interaction.
    return UserContext(message="Hello. How are you feeling today?",
                       help_message="Say Good or Bad, please.",
                       input_options=(
                           InputOption("Good", hipchat_user_feeling_good),
                           InputOption("Bad", hipchat_user_feeling_bad)))


def hipchat_user_feeling_good(_: CommandMessage) -> str:
    # Just return text to reply and end conversation.
    return "Good to hear that."


def hipchat_user_feeling_bad(_: CommandMessage) -> UserContext:
    # Return UserContext instance to continue the conversation
    return UserContext(message="Are you sick?",
                       help_message="Say Yes or No, please.",
                       input_options=(
                           InputOption("Yes", hipchat_user_sick),
                           InputOption("No", hipchat_user_not_sick)))


def hipchat_user_sick(_: CommandMessage) -> str:
    return "I'm sorry to hear that. Hope you get better, soon."


def hipchat_user_not_sick(_: CommandMessage) -> str:
    return "So you are just not feeling well. O.K., then."
