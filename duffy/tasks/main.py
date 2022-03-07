from typing import Tuple

from celery import Celery

from .. import database
from ..configuration import config
from .base import celery, init_tasks
from .expire import expire_sessions
from .node_pools import NodePool
from .provision import fill_pools

DEFAULT_PERIODIC_INTERVAL = 5 * 60


@celery.on_after_finalize.connect
def setup_periodic_tasks(sender: Celery, **kwargs):
    periodic_config = config.get("tasks", {}).get("periodic", {})

    sender.add_periodic_task(
        periodic_config.get("fill-pools", {}).get("interval", DEFAULT_PERIODIC_INTERVAL),
        fill_pools.signature(),
    )

    sender.add_periodic_task(
        periodic_config.get("expire-sessions", {}).get("interval", DEFAULT_PERIODIC_INTERVAL),
        expire_sessions.signature(),
    )


@celery.on_after_finalize.connect
def run_init_tasks(sender: Celery, **kwargs):
    fill_pools.delay().forget()
    expire_sessions.delay().forget()


def start_worker(worker_args: Tuple[str]):
    database.init_sync_model()
    init_tasks()
    NodePool.process_configuration()

    celery.worker_main(("worker",) + worker_args)
