from unittest import mock

import pytest

from duffy.database import setup

from ..util import noop_context

TEST_CONFIG = {
    "database": {
        "sqlalchemy": {
            "sync_url": "boo",
        }
    }
}


@pytest.mark.parametrize("db_empty", (True, False))
@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.setup.alembic.command.stamp")
@mock.patch("duffy.database.setup.alembic.config.Config")
@mock.patch("duffy.database.setup.metadata")
@mock.patch("duffy.database.setup.inspect")
@mock.patch("duffy.database.setup.get_sync_engine")
def test_setup_db_schema(get_sync_engine, inspect, metadata, Config, stamp, db_empty):
    engine = mock.MagicMock()
    get_sync_engine.return_value = engine

    inspection_result = mock.MagicMock()
    inspection_result.has_table.return_value = not db_empty
    metadata.tables = {"table1": object(), "table2": object()}
    inspect.return_value = inspection_result

    cfg = mock.MagicMock()
    Config.return_value = cfg

    if db_empty:
        expectation = noop_context()
    else:
        expectation = pytest.raises(SystemExit)

    with expectation:
        setup.setup_db_schema()

    if db_empty:
        get_sync_engine.assert_called_once_with()
        engine.begin.assert_called_once_with()
        metadata.create_all.assert_called_once_with(bind=engine)
        cfg.set_main_option.assert_any_call("script_location", str(setup.HERE / "migrations"))
        cfg.set_main_option.assert_any_call("sqlalchemy.url", "boo")
        stamp.assert_called_once_with(cfg, "head")
    else:
        engine.begin.assert_not_called()
        metadata.create_all.assert_not_called()
        Config.assert_not_called()
