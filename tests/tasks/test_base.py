from unittest import mock

from celery import Celery

from duffy.tasks import base


def test_celery():
    assert isinstance(base.celery, Celery)


@mock.patch.dict("duffy.tasks.base.config", clear=True)
@mock.patch("duffy.tasks.base.celery")
def test_init_tasks(celery):
    sentinel = object()
    base.config["tasks"] = {"celery": sentinel}

    base.init_tasks()

    celery.config_from_object.assert_called_once_with(sentinel)
