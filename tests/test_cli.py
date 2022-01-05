import copy
from pathlib import Path
from unittest import mock

import click
import pytest
import yaml
from click.testing import CliRunner

from duffy.cli import cli
from duffy.exceptions import DuffyConfigurationError
from duffy.util import merge_dicts
from duffy.version import __version__

HERE = Path(__file__).parent
EXAMPLE_CONFIG_FILE = HERE.parent / "etc" / "duffy-example-config.yaml"
with EXAMPLE_CONFIG_FILE.open("r") as fp:
    EXAMPLE_CONFIG = {}
    for config_doc in yaml.safe_load_all(fp):
        EXAMPLE_CONFIG = merge_dicts(EXAMPLE_CONFIG, config_doc)


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


def test_cli_missing_config(tmp_path):
    missing_config_file = tmp_path / "missing_duffy_config.yaml"
    runner = CliRunner()
    result = runner.invoke(cli, [f"--config={missing_config_file.absolute()}"])
    assert result.exit_code == 1
    assert isinstance(result.exception, FileNotFoundError)


@pytest.mark.parametrize("testcase", ("normal", "test-data", "config-error"))
@mock.patch("duffy.cli.setup_db_test_data")
@mock.patch("duffy.cli.setup_db_schema")
def test_setup_db(setup_db_schema, setup_db_test_data, testcase, caplog):
    if testcase == "config-error":
        setup_db_schema.side_effect = DuffyConfigurationError("database")
    runner = CliRunner()
    args = [f"--config={EXAMPLE_CONFIG_FILE.absolute()}", "setup-db"]
    if testcase == "test-data":
        args.append("--test-data")
    result = runner.invoke(cli, args)
    setup_db_schema.assert_called_once_with()
    if testcase != "config-error":
        assert result.exit_code == 0
        if testcase == "test-data":
            setup_db_test_data.assert_called_once_with()
    else:
        assert result.exit_code != 0
        assert "Configuration key missing or wrong: database" in caplog.messages


@pytest.mark.parametrize(
    "config_error, shell_type",
    [(False, st) for st in (None, "python", "ipython", "bad shell type")] + [(True, None)],
)
@pytest.mark.duffy_config(EXAMPLE_CONFIG, clear=True)
@mock.patch("duffy.shell.embed_shell")
@mock.patch("duffy.database.init_model")
def test_shell(init_model, embed_shell, duffy_config_files, config_error, shell_type):
    # Ensure it's only one config file.
    (config_file,) = duffy_config_files

    _shell_type = shell_type or ""

    if config_error:
        config = copy.deepcopy(EXAMPLE_CONFIG)
        del config["database"]
        with config_file.open("w") as fp:
            yaml.dump(config, fp)

    args = [f"--config={config_file.absolute()}", "shell"]

    if shell_type:
        args.append(f"--shell-type={shell_type}")

    if config_error:
        init_model.side_effect = DuffyConfigurationError("database")

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


@mock.patch("duffy.cli.start_worker")
def test_worker(start_worker):
    runner = CliRunner()

    result = runner.invoke(
        cli, [f"--config={EXAMPLE_CONFIG_FILE.absolute()}", "worker", "a", "-b", "c", "--dee"]
    )

    assert result.exit_code == 0
    start_worker.assert_called_once_with(worker_args=("a", "-b", "c", "--dee"))


@pytest.mark.duffy_config(EXAMPLE_CONFIG, clear=True)
@pytest.mark.parametrize("testcase", ("default", "with-options", "missing-logging-config"))
@mock.patch("duffy.cli.uvicorn.run")
def test_serve(uvicorn_run, testcase, duffy_config_files):
    (config_file,) = duffy_config_files

    if testcase in ("default", "missing-logging-config"):
        parameters = (f"--config={config_file.absolute()}", "serve")
    elif testcase == "with-options":
        parameters = (
            f"--config={config_file.absolute()}",
            "serve",
            "--host=127.0.0.1",
            "--port=8080",
            "--loglevel=info",
        )

    if testcase == "missing-logging-config":
        config = copy.deepcopy(EXAMPLE_CONFIG)
        del config["app"]["logging"]
        with config_file.open("w") as fp:
            yaml.dump(config, fp)

    runner = CliRunner()
    result = runner.invoke(cli, parameters)
    assert result.exit_code == 0
    uvicorn_run.assert_called_once()


@pytest.mark.duffy_config(EXAMPLE_CONFIG, clear=True)
@pytest.mark.parametrize("testcase", ("default", "with-options", "missing-logging-config"))
@mock.patch("duffy.cli.uvicorn.run")
def test_serve_legacy(uvicorn_run, testcase, duffy_config_files):
    (config_file,) = duffy_config_files

    if testcase in ("default", "missing-logging-config"):
        parameters = (f"--config={config_file.absolute()}", "serve-legacy")
    elif testcase == "with-options":
        parameters = (
            f"--config={config_file.absolute()}",
            "serve-legacy",
            "--host=127.0.0.1",
            "--port=9090",
            "--dest=http://127.0.0.1:8080",
            "--loglevel=info",
        )

    if testcase == "missing-logging-config":
        config = copy.deepcopy(EXAMPLE_CONFIG)
        del config["metaclient"]["logging"]
        with config_file.open("w") as fp:
            yaml.dump(config, fp)

    runner = CliRunner()
    result = runner.invoke(cli, parameters)
    assert result.exit_code == 0
    uvicorn_run.assert_called_once()
