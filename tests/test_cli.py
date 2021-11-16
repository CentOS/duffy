from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from duffy.cli import main
from duffy.version import __version__

HERE = Path(__file__).parent
EXAMPLE_CONFIG = HERE.parent / "etc" / "duffy-example-config.yaml"


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert result.output == "Duffy, version %s\n" % __version__


def test_cli_help():
    """Ensure `duffy --help` works."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"], terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: duffy" in result.output


def test_cli_suggestion():
    runner = CliRunner()
    result = runner.invoke(main, ["--helo"])
    assert result.exit_code == 2
    assert "Error: No such option: --helo" in result.output


@pytest.mark.parametrize(
    "parameters", ((), ("--host=127.0.0.1",), (f"--config={EXAMPLE_CONFIG.absolute()}",))
)
@mock.patch("duffy.cli.uvicorn.run")
def test_cli_main(uvicorn_run, parameters):
    runner = CliRunner()
    runner.invoke(main, parameters)
    uvicorn_run.assert_called_once()
