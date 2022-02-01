from unittest import mock

import pytest

from duffy.tasks import main

TEST_CONFIG = {
    "tasks": {
        "celery": {
            "broker_url": "redis://localhost:6379",
            "result_backend": "redis://localhost:6379",
        },
        "periodic": {"fill-pools": {"interval": 5}},
    }
}


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.tasks.main.fill_pools")
def test_setup_periodic_tasks(fill_pools):
    sender = mock.MagicMock()
    fill_pools.signature.return_value = sentinel = object()

    main.setup_periodic_tasks(sender)

    fill_pools.signature.assert_called_once_with()
    sender.add_periodic_task.assert_called_once_with(
        TEST_CONFIG["tasks"]["periodic"]["fill-pools"]["interval"], sentinel
    )


@mock.patch("duffy.tasks.main.fill_pools")
def test_run_init_tasks(fill_pools):
    fill_pools.delay.return_value = delayed_task = mock.Mock()

    main.run_init_tasks(None)

    fill_pools.delay.assert_called_once_with()
    delayed_task.forget.assert_called_once_with()


@mock.patch("duffy.tasks.main.celery")
@mock.patch("duffy.tasks.main.NodePool")
@mock.patch("duffy.tasks.main.init_tasks")
@mock.patch("duffy.tasks.main.database")
def test_start_worker(database, init_tasks, NodePool, celery):
    """Test that start_worker() passes on arguments to Celery."""
    worker_args = ("foo", "--bar")
    main.start_worker(worker_args=worker_args)

    database.init_sync_model.assert_called_once_with()
    init_tasks.assert_called_once_with()
    NodePool.process_configuration.assert_called_once_with()

    celery.worker_main.assert_called_once_with(("worker",) + worker_args)
