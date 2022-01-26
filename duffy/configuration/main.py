from pathlib import Path
from typing import List, Union

import yaml

from .validation import ConfigModel

SYSTEM_CONFIG_FILE = "/etc/duffy.yaml"

config = {}

DEFAULT_CONFIG = {
    "loglevel": "warning",
    "host": "127.0.0.1",
    "port": 8080,
}


def read_configuration(*config_files: List[Union[Path, str]]):
    config.clear()
    config.update(DEFAULT_CONFIG)
    for config_file in config_files:
        if not isinstance(config_file, Path):
            config_file = Path(config_file)
        with config_file.open("r") as fp:
            for config_doc in yaml.safe_load_all(fp):
                # validate configuration file
                ConfigModel(**config_doc)

                config.update(config_doc)
