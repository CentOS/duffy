from typing import Tuple

from celery import Celery

from .configuration import config

app = Celery("duffy.tasks")


@app.task
def check_pools():
    print("Checking pools...")


def start_worker(worker_args: Tuple[str]):
    app.config_from_object(config["celery"])
    app.worker_main(("-A", "duffy.tasks", "worker") + worker_args)
