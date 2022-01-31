from typing import Tuple

from .. import database
from ..configuration import config
from .base import celery


def start_worker(worker_args: Tuple[str]):
    database.init_sync_model()

    celery.config_from_object(config["celery"])
    celery.worker_main(("worker",) + worker_args)
