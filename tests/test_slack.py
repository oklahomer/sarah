# -*- coding: utf-8 -*-
import types
import pytest
import sarah
from sarah.slack import Slack, SlackClient, SarahSlackException
from mock import patch


class TestInit(object):
    def test_init(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(),
                      max_workers=1)

        assert isinstance(slack.client, SlackClient)
        assert slack.client.token == 'spam_ham_egg'
        assert slack.message_id == 0
        assert slack.ws is None

    def test_load_plugins(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.plugins.simple_counter', {}),
                               ('sarah.plugins.echo', {})),
                      max_workers=1)
        slack.load_plugins(slack.plugins)

        assert list(slack.commands.keys()) == ['.count',
                                               '.reset_count',
                                               '.echo']

        commands = list(slack.commands.values())

        assert commands[0].name == '.count'
        assert commands[0].module_name == 'sarah.plugins.simple_counter'
        assert isinstance(commands[0].function, types.FunctionType) is True

        assert commands[1].name == '.reset_count'
        assert commands[1].module_name == 'sarah.plugins.simple_counter'
        assert isinstance(commands[1].function, types.FunctionType) is True

        assert commands[2].name == '.echo'
        assert commands[2].module_name == 'sarah.plugins.echo'
        assert isinstance(commands[2].function, types.FunctionType) is True

    def test_non_existing_plugin(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)
        slack.load_plugins(slack.plugins)
        assert len(slack.commands) == 0
        assert len(slack.scheduler.get_jobs()) == 0

    def test_connection_fail(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'request',
                          side_effect=Exception) as _mock_request:
            with pytest.raises(SarahSlackException) as e:
                slack.connect()
            assert _mock_request.call_count == 1
            assert e.value.args[0] == "Slack request error on /rtm.start. "

    def test_connection_response_error(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'get',
                          return_value={"dummy": "spam"}) as _mock_request:
            with pytest.raises(SarahSlackException) as e:
                slack.connect()
            assert _mock_request.call_count == 1
            assert e.value.args[0] == ("Slack response did not contain "
                                       "connecting url. {'dummy': 'spam'}")

    def test_connection_ok(self):
        slack = Slack(token='spam_ham_egg',
                      plugins=(('spam.ham.egg.onion', {}),),
                      max_workers=1)

        with patch.object(slack.client,
                          'get',
                          return_value={'url': 'ws://localhost:80/'}):
            with patch.object(sarah.slack.WebSocketApp,
                              'run_forever',
                              return_value=True) as _mock_connect:
                slack.connect()
                assert _mock_connect.call_count == 1
