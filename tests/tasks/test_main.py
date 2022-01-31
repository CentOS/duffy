from unittest import mock

import pytest

from duffy.tasks import main

CELERY_CONFIG = {
    "broker_url": "redis://localhost:6379",
    "result_backend": "redis://localhost:6379",
}


@pytest.mark.duffy_config({"celery": CELERY_CONFIG})
@mock.patch("duffy.tasks.main.celery")
@mock.patch("duffy.tasks.main.database")
def test_start_worker(database, celery):
    """Test that start_worker() passes on arguments to Celery."""
    worker_args = ("foo", "--bar")
    main.start_worker(worker_args=worker_args)

    database.init_sync_model.assert_called_once_with()

    celery.config_from_object.assert_called_once_with(CELERY_CONFIG)
    celery.worker_main.assert_called_once_with(("worker",) + worker_args)
