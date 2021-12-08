from unittest import mock

import pytest

from duffy import tasks

CELERY_CONFIG = {
    "broker_url": "redis://localhost:6379",
    "result_backend": "redis://localhost:6379",
}


def test_check_pools(capsys):
    """Check that check_pools() works."""
    # This is currently a no-op, check_pools() is just a stand-in function.

    tasks.check_pools()

    stdout, stderr = capsys.readouterr()
    assert "Checking pools..." in stdout
    assert stderr == ""


@pytest.mark.duffy_config({"celery": CELERY_CONFIG})
@mock.patch("duffy.tasks.app")
def test_start_worker(app):
    """Test that start_worker() passes on arguments to Celery."""
    worker_args = ("foo", "--bar")
    tasks.start_worker(worker_args=worker_args)

    app.config_from_object.assert_called_once_with(CELERY_CONFIG)
    app.worker_main.assert_called_once_with(("-A", "duffy.tasks", "worker") + worker_args)
