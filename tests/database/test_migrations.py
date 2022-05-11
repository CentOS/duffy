from pathlib import Path
from types import MethodType
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
    @mock.patch.object(alembic_migration, "_get_current")
    def test_create(self, _get_current, alembic_command, autogenerate, caplog):
        comment = "BOOP"

        with caplog.at_level("DEBUG"):
            alembic_migration.create(comment, autogenerate)

        alembic_command.revision.assert_called_once_with(
            config=alembic_migration.config, message=comment, autogenerate=autogenerate
        )

        if autogenerate:
            assert any("remember" in msg.lower() for msg in caplog.messages)

    @mock.patch("alembic.script.ScriptDirectory")
    def test__get_current(self, ScriptDirectory):
        ScriptDirectory.from_config.return_value = script = mock.MagicMock()
        rev = mock.MagicMock()
        rev.cmd_format.return_value = formatted_rev = object()
        script.get_all_current.return_value = [rev]

        def run_env(self):
            self.env.fn(rev, None)

        script.run_env = mock.MagicMock(wraps=MethodType(run_env, script))

        class FakeEnvCtx:
            def __init__(self, config, script, fn, **kwargs):
                self.config = config
                self.script = script
                script.env = self
                self.fn = fn

            def __enter__(self):
                return self

            def __exit__(self, type, value, traceback):
                pass

        with mock.patch(
            "alembic.runtime.environment.EnvironmentContext", wraps=FakeEnvCtx
        ) as ctxmgr:
            result = alembic_migration._get_current()

        ScriptDirectory.from_config.assert_called_once_with(alembic_migration.config)
        script.get_all_current.assert_called_once_with(rev)
        rev.cmd_format.assert_called_once_with(verbose=False)
        ctxmgr.assert_called_once()
        script.run_env.assert_called_once_with()

        assert result == {formatted_rev}

    @mock.patch.object(alembic_migration, "_get_current")
    def test_db_version(self, _get_current):
        alembic_migration.db_version()

        _get_current.assert_called_once_with()

    @pytest.mark.parametrize("things_changed", (True, False))
    @pytest.mark.parametrize("method", ("upgrade", "downgrade"))
    @mock.patch("duffy.database.migrations.main.alembic.command")
    @mock.patch.object(alembic_migration, "_get_current")
    def test_upgrade_downgrade(self, _get_current, alembic_command, method, things_changed, capsys):
        if things_changed:
            _get_current.side_effect = [{"BOO"}, {"BAH"}]
        else:
            _get_current.side_effect = [{"BOO"}, {"BOO"}]

        getattr(alembic_migration, method)("version")

        getattr(alembic_command, method).assert_called_once_with(
            alembic_migration.config, "version"
        )

        captured = capsys.readouterr()

        if things_changed:
            assert f"{method.title()}d to: BAH" in captured.out
        else:
            assert f"Nothing to {method}." in captured.out
