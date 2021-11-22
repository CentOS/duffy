from pathlib import Path
from unittest import mock

import click
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
    "config_error, shell_type",
    [(False, st) for st in (None, "python", "ipython", "bad shell type")] + [(True, None)],
)
@mock.patch("duffy.shell.embed_shell")
@mock.patch("duffy.database.init_model")
def test_shell(init_model, embed_shell, config_error, shell_type):
    _shell_type = shell_type or ""
    args = ["shell"]
    if not config_error:
        args.insert(0, f"--config={EXAMPLE_CONFIG.absolute()}")
    if shell_type:
        args.append(f"--shell-type={shell_type}")

    if config_error:
        init_model.side_effect = DuffyConfigurationError(
            "Configuration key missing or wrong: database"
        )

    runner = CliRunner()

    # Act as if IPython is always available, i.e. don't auto-detect the allowed values for
    # the --shell-type option.

    # First, dig out the relevant click.Option object, ...
    shell_type_option = [o for o in cli.commands["shell"].params if o.name == "shell_type"][0]
    # ... then temporarily mock its type with a click.Choice of a static list.
    with mock.patch.object(shell_type_option, "type", new=click.Choice(["python", "ipython"])):
        result = runner.invoke(cli, args)

    if not config_error and "bad" not in _shell_type:
        assert result.exit_code == 0
        embed_shell.assert_called_once_with(shell_type=shell_type)
    else:
        assert result.exit_code != 0
        embed_shell.assert_not_called()

    if "bad" not in _shell_type:  # this is sorted out in click before the CLI function gets called
        init_model.assert_called_once_with()
    else:
        init_model.assert_not_called()


@pytest.mark.parametrize(
    "config_error, parameters",
    [
        (False, parms)
        for parms in (
            ("serve",),
            ("serve", "--host=127.0.0.1"),
            (f"--config={EXAMPLE_CONFIG.absolute()}", "serve"),
        )
    ]
    + [(True, ("serve",))],
)
@mock.patch("duffy.database.init_model")
@mock.patch("duffy.cli.uvicorn.run")
def test_serve(uvicorn_run, init_model, config_error, parameters):
    if config_error:
        init_model.side_effect = DuffyConfigurationError("database")
    runner = CliRunner()
    result = runner.invoke(cli, parameters)
    init_model.assert_called_once()
    if not config_error:
        assert result.exit_code == 0
        uvicorn_run.assert_called_once()
    else:
        assert result.exit_code != 0
        uvicorn_run.assert_not_called()
