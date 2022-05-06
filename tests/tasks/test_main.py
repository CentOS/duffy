from unittest import mock

import pytest

from duffy.configuration import config
from duffy.tasks import main

TEST_CONFIG = {
    "tasks": {
        "celery": {
            "broker_url": "redis://localhost:6379",
            "result_backend": "redis://localhost:6379",
        },
        "locking": {"url": "redis:///"},
        "periodic": {"fill-pools": {"interval": 5}, "expire-sessions": {"interval": 7}},
    }
}


@pytest.mark.duffy_config(TEST_CONFIG)
@pytest.mark.parametrize("period_type", ("dimensionless", "complex"))
@mock.patch("duffy.tasks.main.expire_sessions")
@mock.patch("duffy.tasks.main.fill_pools")
def test_setup_periodic_tasks(fill_pools, expire_sessions, period_type):
    sender = mock.MagicMock()
    fill_pools.signature.return_value = fill_pools_sentinel = object()
    expire_sessions.signature.return_value = expire_sessions_sentinel = object()

    if period_type == "dimensionless":
        expected_fill_pool_schedule = TEST_CONFIG["tasks"]["periodic"]["fill-pools"]["interval"]
        expected_expire_sessions_schedule = TEST_CONFIG["tasks"]["periodic"]["expire-sessions"][
            "interval"
        ]
    else:
        config["tasks"]["periodic"]["fill-pools"]["interval"] = "5m"
        expected_fill_pool_schedule = 300
        config["tasks"]["periodic"]["expire-sessions"]["interval"] = "7m"
        expected_expire_sessions_schedule = 420

    main.setup_periodic_tasks(sender)

    fill_pools.signature.assert_called_once_with()
    expire_sessions.signature.assert_called_once_with()
    sender.add_periodic_task.assert_has_calls(
        [
            mock.call(expected_fill_pool_schedule, fill_pools_sentinel),
            mock.call(expected_expire_sessions_schedule, expire_sessions_sentinel),
        ],
        any_order=True,
    )


@mock.patch("duffy.tasks.main.expire_sessions")
@mock.patch("duffy.tasks.main.fill_pools")
def test_run_init_tasks(fill_pools, expire_sessions):
    fill_pools.delay.return_value = fill_pools_result = mock.Mock()
    expire_sessions.delay.return_value = expire_sessions_result = mock.Mock()

    main.run_init_tasks(None)

    fill_pools.delay.assert_called_once_with()
    fill_pools_result.forget.assert_called_once_with()
    expire_sessions.delay.assert_called_once_with()
    expire_sessions_result.forget.assert_called_once_with()


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
