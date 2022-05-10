from pathlib import Path
from unittest import mock

import pytest

from duffy.configuration import config
from duffy.database.migrations.main import alembic_migration

HERE = Path(__file__).parent
MIGRATIONSDIR = HERE.parent.parent / "duffy" / "database" / "migrations"


@pytest.mark.duffy_config(
    {"database": {"sqlalchemy": {"sync_url": "sync://url", "async_url": "async://url"}}}
)
class TestAlembicMigration:
    def test_config(self):
        if hasattr(alembic_migration, "_config"):
            del alembic_migration._config

        assert alembic_migration.config.get_main_option("script_location") == str(
            MIGRATIONSDIR.absolute()
        )
        assert alembic_migration.config.get_main_option("sqlalchemy.url") == "sync://url"

    def test_config_with_percent_signs(self):
        if hasattr(alembic_migration, "_config"):
            del alembic_migration._config

        sqla_config = config["database"]["sqlalchemy"]
        sqla_config["sync_url"] += "/%"
        MIGRATIONSDIR_WITH_PERCENT = MIGRATIONSDIR / "%"

        with mock.patch("duffy.database.migrations.main.HERE", MIGRATIONSDIR_WITH_PERCENT):
            assert alembic_migration.config.get_main_option("script_location") == str(
                MIGRATIONSDIR_WITH_PERCENT.absolute()
            )
            assert alembic_migration.config.get_main_option("sqlalchemy.url") == "sync://url/%"

    @pytest.mark.parametrize("autogenerate", (False, True))
    @mock.patch("duffy.database.migrations.main.alembic.command")
    def test_create(self, alembic_command, autogenerate, caplog):
        comment = "BOOP"

        with caplog.at_level("DEBUG"):
            alembic_migration.create(comment, autogenerate)

        alembic_command.revision.assert_called_once_with(
            config=alembic_migration.config, message=comment, autogenerate=autogenerate
        )

        if autogenerate:
            assert any("remember" in msg.lower() for msg in caplog.messages)

    @mock.patch("duffy.database.migrations.main.alembic.command")
    def test_db_version(self, alembic_command):
        alembic_migration.db_version()

        alembic_command.current.assert_called_once_with(alembic_migration.config)

    @pytest.mark.parametrize("method", ("upgrade", "downgrade"))
    @mock.patch("duffy.database.migrations.main.alembic.command")
    def test_upgrade_downgrade(self, alembic_command, method):
        getattr(alembic_migration, method)("version")

        getattr(alembic_command, method).assert_called_once_with(
            alembic_migration.config, "version"
        )
