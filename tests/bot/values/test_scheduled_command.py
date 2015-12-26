# -*- coding: utf-8 -*-
from assertpy import assert_that

from sarah.bot.values import CommandConfig, ScheduledCommand


class DummyClass(object):
    @staticmethod
    def scheduled_job(config: CommandConfig) -> str:
        return config.get('spam', None)


class TestScheduledCommand(object):
    def test_valid(self):
        scheduled_command = ScheduledCommand(DummyClass.scheduled_job.__name__,
                                             DummyClass.scheduled_job,
                                             DummyClass.__name__,
                                             {'spam': "ham"},
                                             {'trigger': "cron",
                                              'hour': 10,
                                              'minute': 30})

        assert_that(scheduled_command.name) \
            .is_equal_to(DummyClass.scheduled_job.__name__)
        assert_that(scheduled_command.function) \
            .is_equal_to(DummyClass.scheduled_job)
        assert_that(scheduled_command.module_name) \
            .is_equal_to(DummyClass.__name__)
        assert_that(scheduled_command.config).is_equal_to({'spam': "ham"})
        assert_that(scheduled_command.schedule_config) \
            .is_equal_to({'trigger': "cron",
                          'hour': 10,
                          'minute': 30})
        assert_that(scheduled_command.job_id) \
            .is_equal_to("%s.%s" % (DummyClass.__name__,
                                    DummyClass.scheduled_job.__name__))

        # is callable
        assert_that(scheduled_command()).is_equal_to("ham")
