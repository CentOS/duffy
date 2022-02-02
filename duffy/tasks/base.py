from celery import Celery

from ..configuration import config

celery = Celery("duffy.tasks")


def init_tasks():
    celery.config_from_object(config["tasks"]["celery"])
