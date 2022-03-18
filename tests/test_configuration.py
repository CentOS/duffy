import copy
from pathlib import Path

import pytest
import yaml

from duffy.configuration import main
from duffy.util import merge_dicts

EXAMPLE_CONFIG = {"app": {"host": "127.0.0.1", "port": 8080}}


@pytest.mark.duffy_config(EXAMPLE_CONFIG, clear=True)
class TestConfiguration:
    @pytest.mark.parametrize("objtype", (str, Path))
    def test__expand_normalize_config_files(self, objtype, tmp_path, duffy_config_files):
        (config_file,) = duffy_config_files

        sub_file1 = tmp_path / "sub_file1.yaml"
        sub_file1.touch()

        sub_file2 = tmp_path / "sub_file2.yaml"
        sub_file2.touch()

        config_files = [config_file, tmp_path]
        expanded_config_files = main._expand_normalize_config_files(
            [objtype(f) for f in config_files]
        )

        assert expanded_config_files == [config_file, sub_file1, sub_file2]

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

    @pytest.mark.duffy_config({"app": {}})
    def test_read_configuration_partial(self, duffy_config_files, tmp_path):
        assert main.config == EXAMPLE_CONFIG

    @pytest.mark.duffy_config(example_config=True, clear=True)
    def test_read_configuration_partial_validate_post(self, duffy_config_files, tmp_path):
        partial_config_file = tmp_path / "partial-config.yaml"
        with partial_config_file.open("w") as fp:
            yaml.dump({"metaclient": {}}, fp)

        main.read_configuration(partial_config_file, clear=True, validate=False)
        main.read_configuration(*duffy_config_files, clear=False, validate=False)
        main.read_configuration(clear=False, validate=True)
