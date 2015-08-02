# -*- coding: utf-8 -*-
import logging
import types
from apscheduler.triggers.interval import IntervalTrigger
import pytest
import sarah
from sarah.slack import Slack, SlackClient, SarahSlackException
from mock import patch, MagicMock, call


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


class TestSchedule(object):
    def test_missing_config(self):
        logging.warning = MagicMock()

        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.plugins.bmw_quotes',),),
                      max_workers=1)
        slack.connect = lambda: True
        slack.run()

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
            'Missing configuration for schedule job. ' +
            'sarah.plugins.bmw_quotes. Skipping.')

        jobs = slack.scheduler.get_jobs()
        assert len(jobs) == 0

    def test_missing_channel_config(self):
        logging.warning = MagicMock()

        slack = Slack(token='spam_ham_egg',
                      plugins=(('sarah.plugins.bmw_quotes', {}),),
                      max_workers=1)
        slack.connect = lambda: True
        slack.run()

        assert logging.warning.call_count == 1
        assert logging.warning.call_args == call(
            'Missing channels configuration for schedule job. ' +
            'sarah.plugins.bmw_quotes. Skipping.')

        jobs = slack.scheduler.get_jobs()
        assert len(jobs) == 0

    def test_add_schedule_job(self):
        slack = Slack(
            token='spam_ham_egg',
            max_workers=1,
            plugins=(('sarah.plugins.bmw_quotes', {'channels': 'U06TXXXXX'}),))
        slack.connect = lambda: True
        slack.run()

        jobs = slack.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == 'sarah.plugins.bmw_quotes.bmw_quotes'
        assert isinstance(jobs[0].trigger, IntervalTrigger)
        assert jobs[0].trigger.interval_length == 300
        assert isinstance(jobs[0].func, types.FunctionType)
