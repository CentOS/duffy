import copy

import pytest

from duffy.configuration import main
from duffy.util import merge_dicts

EXAMPLE_CONFIG = {"app": {"host": "127.0.0.1", "port": 8080}}


@pytest.mark.duffy_config(EXAMPLE_CONFIG, clear=True)
class TestConfiguration:
    @pytest.mark.parametrize("clear", (True, False))
    def test_read_configuration_clear(self, clear):
        main.read_configuration(clear=clear)
        if clear:
            assert main.config == {}
        else:
            assert main.config == EXAMPLE_CONFIG

    @pytest.mark.duffy_config({}, objtype=str, clear=False)
    def test_read_configuration_str(self, duffy_config_files):
        assert main.config == EXAMPLE_CONFIG

    @pytest.mark.duffy_config({"app": {"loglevel": "debug"}})
    def test_read_configuration_multiple(self, duffy_config_files):
        assert len(duffy_config_files) > 1
        expected_config = copy.deepcopy(EXAMPLE_CONFIG)
        expected_config["app"]["loglevel"] = "debug"
        assert main.config == expected_config

    @pytest.mark.duffy_config({"app": {"host": "host.example.net"}})
    def test_read_configuration_multiple_override(self, duffy_config_files):
        assert len(duffy_config_files) > 1
        assert main.config == merge_dicts(EXAMPLE_CONFIG, {"app": {"host": "host.example.net"}})
