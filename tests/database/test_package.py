from unittest import mock

import pytest

from duffy import configuration, database, exceptions

TEST_CONFIG = {
    "database": {
        "sqlalchemy": {
            "sync_url": "boo",
            "async_url": "boo",
        }
    }
}


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.sync_session_maker")
@mock.patch("duffy.database.get_sync_engine")
def test_init_sync_model(get_sync_engine, sync_session_maker):
    sentinel = object()
    get_sync_engine.return_value = sentinel

    database.init_sync_model()

    get_sync_engine.assert_called_once_with()
    sync_session_maker.configure.assert_called_once_with(bind=sentinel)


@pytest.mark.asyncio
@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.async_session_maker", new_callable=mock.AsyncMock)
@mock.patch("duffy.database.get_async_engine")
async def test_init_async_model(get_async_engine, async_session_maker):
    sentinel = object()
    get_async_engine.return_value = sentinel
    # configure() is not an async coroutine, avoid warning
    async_session_maker.configure = mock.MagicMock()

    await database.init_async_model()

    get_async_engine.assert_called_once_with()
    async_session_maker.configure.assert_called_once_with(bind=sentinel)


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
@pytest.mark.parametrize("testcase", ("works", "config-broken"))
@mock.patch("duffy.database.create_engine")
def test_get_sync_engine(create_engine, testcase):
    if testcase == "config-broken":
        del configuration.config["database"]["sqlalchemy"]
        with pytest.raises(exceptions.DuffyConfigurationError):
            database.get_sync_engine()
        create_engine.assert_not_called()
    else:
        database.get_sync_engine()
        create_engine.assert_called_once_with(url="boo")


@pytest.mark.duffy_config(TEST_CONFIG)
@pytest.mark.parametrize("testcase", ("works", "config-broken"))
@mock.patch("duffy.database.create_async_engine")
def test_get_async_engine(create_async_engine, testcase):
    if testcase == "config-broken":
        del configuration.config["database"]["sqlalchemy"]
        with pytest.raises(exceptions.DuffyConfigurationError):
            database.get_async_engine()
        create_async_engine.assert_not_called()
    else:
        database.get_async_engine()
        create_async_engine.assert_called_once_with(url="boo")
