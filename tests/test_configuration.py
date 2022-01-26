from unittest import mock

import pytest

from duffy.configuration import main


@pytest.mark.duffy_config
@mock.patch.dict("duffy.configuration.config", {}, clear=True)
class TestConfiguration:
    @pytest.mark.duffy_config(clear=True)
    def test_read_configuration_default(self):
        main.read_configuration()
        assert main.config == main.DEFAULT_CONFIG

    @pytest.mark.duffy_config({}, objtype=str, clear=True)
    def test_read_configuration_str(self, duffy_config_files):
        main.read_configuration(*duffy_config_files)
        assert main.config == main.DEFAULT_CONFIG

    @pytest.mark.duffy_config({"key": "value"})
    def test_read_configuration_multiple(self, duffy_config_files):
        main.read_configuration(*duffy_config_files)
        assert main.config == {
            **main.DEFAULT_CONFIG,
            **{"key": "value"},
        }

    @pytest.mark.duffy_config({"loglevel": "debug"})
    def test_read_configuration_multiple_override(self, duffy_config_files):
        main.read_configuration(*duffy_config_files)
        assert main.config["loglevel"] == "debug"
