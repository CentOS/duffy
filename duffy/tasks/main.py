from typing import Tuple

from .. import database
from .base import celery, init_tasks
from .node_pools import NodePool


def start_worker(worker_args: Tuple[str]):
    database.init_sync_model()
    init_tasks()
    NodePool.process_configuration()

    celery.worker_main(("worker",) + worker_args)
