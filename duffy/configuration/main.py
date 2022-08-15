from copy import deepcopy
from functools import lru_cache
from itertools import chain
from pathlib import Path
from typing import Any, List, Sequence, Union

import yaml

from ..util import merge_dicts
from .validation import ConfigModel

config = {}


def _expand_normalize_config_files(config_files: List[Union[Path, str]]) -> List[Path]:
    config_file_paths = []

    for path in config_files:
        if not isinstance(path, Path):
            path = Path(path)
        if path.is_dir():
            config_file_paths.extend(sorted(chain(path.glob("*.yaml"), path.glob("*.yml"))))
        else:
            config_file_paths.append(path)

    return config_file_paths


def read_configuration(
    *config_files: Sequence[Union[Path, str]], clear: bool = True, validate: bool = True
):
    config_files = _expand_normalize_config_files(config_files)

    if clear:
        new_config = {}
    else:
        new_config = deepcopy(config)

    for config_file in config_files:
        with config_file.open("r") as fp:
            for config_doc in yaml.safe_load_all(fp):
                if not config_doc:
                    continue
                new_config = merge_dicts(new_config, config_doc)

    if validate:
        # validate merged configuration
        ConfigModel(**new_config)

    config.clear()
    config.update(new_config)


@lru_cache
def config_get(*keys, default: Any = None):
    """Retrieve a configuration value from multiple alternative places."""
    for key in keys:
        item = config
        elems = key.split(".")
        try:
            for elem in elems:
                item = item[elem]
        except KeyError:
            continue
        else:
            return item

    return default
