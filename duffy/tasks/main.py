from typing import Tuple

from .. import database
from .base import celery, init_tasks


def start_worker(worker_args: Tuple[str]):
    database.init_sync_model()
    init_tasks()

    celery.worker_main(("worker",) + worker_args)
