from pathlib import Path
from typing import List, Union

import yaml

from ..util import merge_dicts
from .validation import ConfigModel

config = {}


def read_configuration(*config_files: List[Union[Path, str]], clear: bool = True):
    new_config = {}
    for config_file in config_files:
        if not isinstance(config_file, Path):
            config_file = Path(config_file)
        with config_file.open("r") as fp:
            for config_doc in yaml.safe_load_all(fp):
                # validate configuration file
                ConfigModel(**config_doc)

                new_config = merge_dicts(new_config, config_doc)

    if clear:
        config.clear()

    config.update(new_config)
