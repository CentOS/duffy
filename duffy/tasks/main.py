from typing import Tuple

from ..configuration import config
from .base import celery


def start_worker(worker_args: Tuple[str]):
    celery.config_from_object(config["celery"])
    celery.worker_main(("worker",) + worker_args)
