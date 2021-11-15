from unittest import mock

import pytest

from duffy.database import setup

TEST_CONFIG = {
    "database": {
        "sqlalchemy": {
            "sync_url": "boo",
        }
    }
}


@pytest.mark.duffy_config(TEST_CONFIG)
@mock.patch("duffy.database.setup.alembic.command.stamp")
@mock.patch("duffy.database.setup.alembic.config.Config")
@mock.patch("duffy.database.setup.metadata")
@mock.patch("duffy.database.setup.get_sync_engine")
def test_setup_db_schema(get_sync_engine, metadata, Config, stamp):
    engine = mock.MagicMock()
    get_sync_engine.return_value = engine

    cfg = mock.MagicMock()
    Config.return_value = cfg

    setup.setup_db_schema()

    get_sync_engine.assert_called_once_with()
    engine.begin.assert_called_once_with()
    metadata.create_all.assert_called_once_with(bind=engine)
    cfg.set_main_option.assert_any_call("script_location", str(setup.HERE / "migrations"))
    cfg.set_main_option.assert_any_call("sqlalchemy.url", "boo")
    stamp.assert_called_once_with(cfg, "head")
