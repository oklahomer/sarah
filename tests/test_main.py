# -*- coding: utf-8 -*-
import os
import pytest
from sarah.main import Sarah, SarahException


class TestInit(object):
    def test_valid_config(self):
        valid_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'resource',
                                  'config',
                                  'valid.yaml')
        sarah = Sarah(config_paths=[valid_path])
        assert type(sarah.config) == dict
        assert 'hipchat' in sarah.config

    def test_non_existing_paths(self):
        non_existing_paths = [os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'non_existing_file.yaml')]
        with pytest.raises(SarahException) as e:
            Sarah(config_paths=non_existing_paths)
        assert e.value.args[0] == 'Configuration file does not exist. %s' % (
            non_existing_paths[0])