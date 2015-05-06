# -*- coding: utf-8 -*-

import os
import pytest
from pytest_bdd import scenario, when, then
from sarah.main import Sarah, SarahException
from hamcrest import assert_that, calling, raises


@pytest.fixture
def initial_args():
    return dict()


@scenario('features/boot.feature', 'Invalid setting')
def test():
    pass


@when('Provided configuration file path is invalid')
def init_with_wrong_path(initial_args):
    initial_args['config_paths'] = [os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'non_existing_file.conf')]


@then('Raise exception')
def raised_exception(initial_args):
    func = lambda: Sarah(**initial_args)
    assert_that(calling(func),
                raises(SarahException,
                       'Configuration file does not exist. %s' %
                       initial_args['config_paths'][0]))
