import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator, List, Union

import pytest
import yaml

from duffy.configuration import read_configuration


def pytest_configure(config):
    config.addinivalue_line("markers", "duffy_config")


@pytest.fixture
def duffy_config_files(request: pytest.FixtureRequest) -> Iterator[List[Union[Path, str]]]:
    configs = []

    # Consult markers about desired configuration files and their contents.

    # request.node.iter_markers() lists markers of parent objects later, we need them early to make
    # e.g. markers on the method override those of the class.
    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "duffy_config":
                if marker.kwargs.get("clear"):
                    configs = []
                objtype = marker.kwargs.get("objtype", Path)
                assert objtype in (Path, str)
                for content in marker.args:
                    assert any(isinstance(content, t) for t in (dict, str))
                    configs.append((objtype, content))

    # Create configuration files.
    config_file_objs = []  # the NamedTemporaryFile objects
    config_file_paths = []  # their Path or str counterparts
    for objtype, content in configs:
        config_file_obj = NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".yaml", prefix="tmp_duffy_test_config", delete=False
        )
        if isinstance(content, dict):
            yaml.dump(content, stream=config_file_obj)
        else:
            print(content, file=config_file_obj)
        config_file_obj.close()
        config_file_objs.append(config_file_obj)
        config_file_paths.append(objtype(config_file_obj.name))

    # Let tests work with the configuration files.
    yield config_file_paths

    # Remove the files.
    for config_file_obj in config_file_objs:
        os.unlink(config_file_obj.name)


@pytest.fixture(autouse=True)
def duffy_config(duffy_config_files):
    read_configuration(*duffy_config_files)
