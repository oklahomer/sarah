# -*- coding: utf-8 -*-
from assertpy import assert_that

from sarah.bot.values import CommandMessage


class TestCommandMessage(object):
    def test_valid(self):
        command_message = CommandMessage(".hello sarah", "sarah", "homer")

        assert_that(command_message.original_text).is_equal_to(".hello sarah")
        assert_that(command_message.text).is_equal_to("sarah")
        assert_that(command_message.sender).is_equal_to("homer")
