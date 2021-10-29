from unittest import mock

import pytest

from duffy import configuration


@pytest.mark.duffy_config
@mock.patch.dict("duffy.configuration.config", {}, clear=True)
class TestConfiguration:
    @pytest.mark.duffy_config(clear=True)
    def test_read_configuration_default(self):
        configuration.read_configuration()
        assert configuration.config == configuration.DEFAULT_CONFIG

    @pytest.mark.duffy_config(objtype=str, clear=True)
    def test_read_configuration_str(self, duffy_config_files):
        configuration.read_configuration(*duffy_config_files)
        assert configuration.config == configuration.DEFAULT_CONFIG

    @pytest.mark.duffy_config({"key": "value"})
    def test_read_configuration_multiple(self, duffy_config_files):
        configuration.read_configuration(*duffy_config_files)
        assert configuration.config == {
            **configuration.DEFAULT_CONFIG,
            **{"key": "value"},
        }

    @pytest.mark.duffy_config({"loglevel": "debug"})
    def test_read_configuration_multiple_override(self, duffy_config_files):
        configuration.read_configuration(*duffy_config_files)
        assert configuration.config["loglevel"] == "debug"
