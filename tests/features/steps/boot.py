# -*- coding: utf-8 -*-

import os
from behave import when, then
from sarah.main import Sarah, SarahException
from hamcrest import assert_that, calling, raises


@when('Provided configuration file path is invalid')
def initialize_with_wrong_config_path(context):
    context.dummy_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'non_existing_file.conf')
    context.func = lambda: Sarah(config_paths=[
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'non_existing_file.conf')
    ])


@then('Raise exception')
def raised_exception(context):
    assert_that(calling(context.func),
                raises(SarahException,
                       'Configuration file does not exist. %s' %
                       context.dummy_file_path))
