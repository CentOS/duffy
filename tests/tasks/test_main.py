from unittest import mock

from duffy.tasks import main


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
