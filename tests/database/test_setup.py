from unittest import mock

from duffy.database import setup


@mock.patch("duffy.database.setup.metadata")
@mock.patch("duffy.database.setup.get_sync_engine")
def test_setup_db_schema(get_sync_engine, metadata):
    engine = mock.MagicMock()
    get_sync_engine.return_value = engine

    setup.setup_db_schema()

    get_sync_engine.assert_called_once_with()
    engine.begin.assert_called_once_with()
    metadata.create_all.assert_called_once_with(bind=engine)
