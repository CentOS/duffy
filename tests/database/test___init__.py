from sys import version_info
from unittest import mock

if not hasattr(mock, "AsyncMock"):
    # This is missing on Python 3.7. The tests will be skipped but ensure that decorators don't
    # break.
    mock.AsyncMock = None

import pytest

from duffy import database

TEST_CONFIG = {
    "database": {
        "sqlalchemy": {
            "sync_url": "boo",
            "async_url": "boo",
        }
    }
}


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.SyncDBSession")
@mock.patch("duffy.database.get_sync_engine")
def test_init_sync_model(get_sync_engine, SyncDBSession):
    sentinel = object()
    get_sync_engine.return_value = sentinel

    database.init_sync_model()

    get_sync_engine.assert_called_once_with()
    SyncDBSession.remove.assert_called_once_with()
    SyncDBSession.configure.assert_called_once_with(bind=sentinel)


@pytest.mark.skipif(version_info < (3, 8), reason="requires Python >= 3.8")
@pytest.mark.asyncio
@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.DBSession", new_callable=mock.AsyncMock)
@mock.patch("duffy.database.get_async_engine")
async def test_init_async_model(get_async_engine, DBSession):
    sentinel = object()
    get_async_engine.return_value = sentinel
    # configure() is not an async coroutine, avoid warning
    DBSession.configure = mock.MagicMock()

    await database.init_async_model()

    get_async_engine.assert_called_once_with()
    if version_info >= (3, 8, 0):
        DBSession.remove.assert_awaited_once_with()
    DBSession.configure.assert_called_once_with(bind=sentinel)


@pytest.mark.skipif(version_info < (3, 8), reason="requires Python >= 3.8")
@pytest.mark.asyncio
@mock.patch("duffy.database.init_async_model")
@mock.patch("duffy.database.init_sync_model")
def test_init_model(init_sync_model, init_async_model):
    sentinel = object()
    init_async_model.return_value = sentinel

    database.init_model(sync_engine=sentinel, async_engine=sentinel)

    init_sync_model.assert_called_once_with(sentinel)
    init_async_model.assert_called_once_with(sentinel)


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.create_engine")
def test_get_sync_engine(create_engine):
    database.get_sync_engine()
    create_engine.assert_called_once_with(url="boo")


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.create_async_engine")
def test_get_async_engine(create_async_engine):
    database.get_async_engine()
    create_async_engine.assert_called_once_with(url="boo")
