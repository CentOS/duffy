from celery import Celery

from duffy.tasks import base


def test_celery():
    assert isinstance(base.celery, Celery)
