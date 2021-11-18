from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from duffy.cli import cli
from duffy.exceptions import DuffyConfigurationError
from duffy.version import __version__

HERE = Path(__file__).parent
EXAMPLE_CONFIG = HERE.parent / "etc" / "duffy-example-config.yaml"


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output == "Duffy, version %s\n" % __version__


def test_cli_help():
    """Ensure `duffy --help` works."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"], terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: duffy" in result.output


def test_cli_suggestion():
    runner = CliRunner()
    result = runner.invoke(cli, ["--helo"])
    assert result.exit_code == 2
    assert "Error: No such option: --helo" in result.output


@mock.patch("duffy.cli.setup_db_schema")
def test_setup_db(setup_db_schema):
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config={EXAMPLE_CONFIG.absolute()}", "setup-db"])
    assert result.exit_code == 0
    setup_db_schema.assert_called_once_with()


@pytest.mark.parametrize(
    "parameters",
    (
        ("serve",),
        ("serve", "--host=127.0.0.1"),
        (f"--config={EXAMPLE_CONFIG.absolute()}", "serve"),
    ),
)
@mock.patch("duffy.database.init_model")
@mock.patch("duffy.cli.uvicorn.run")
def test_cli_serve(uvicorn_run, init_model, parameters):
    runner = CliRunner()
    result = runner.invoke(cli, parameters)
    assert result.exit_code == 0
    init_model.assert_called_once()
    uvicorn_run.assert_called_once()


@mock.patch("duffy.cli.database.init_model")
@mock.patch("duffy.cli.uvicorn.run")
def test_cli_serve_config_broken(uvicorn_run, init_model):
    init_model.side_effect = DuffyConfigurationError("database.sqlalchemy")
    runner = CliRunner()
    result = runner.invoke(cli, ("serve",))
    assert result.exit_code == 1
    init_model.assert_called_once()
    uvicorn_run.assert_not_called()
