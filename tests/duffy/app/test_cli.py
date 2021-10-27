from unittest import mock

import pytest
from click.testing import CliRunner

from duffy.app.cli import main
from duffy.version import __version__


def test_cli_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert result.output == "Duffy, version %s\n" % __version__


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"], terminal_width=80)
    assert result.exit_code == 0
    assert (
        result.output
        == """Usage: main [OPTIONS]

  Duffy is the middle layer running ci.centos.org that manages the provisioning,
  maintenance and teardown / rebuild of the Nodes (physical hardware for now,
  VMs coming soon) that are used to run the tests in the CI Cluster.

Options:
  -p, --portnumb INTEGER          Set the port value [0-65536]
  -6, --ipv6                      Start the server on an IPv6 address
  -4, --ipv4                      Start the server on an IPv4 address
  -l, --loglevel [critical|error|warning|info|debug|trace]
                                  Set the log level
  --version                       Show the version and exit.
  --help                          Show this message and exit.
"""
    )


def test_cli_suggestion():
    runner = CliRunner()
    result = runner.invoke(main, ["--helo"])
    assert result.exit_code == 2
    assert (
        result.output
        == """Usage: main [OPTIONS]
Try 'main --help' for help.

Error: No such option: --helo Did you mean --help?
"""
    )


@pytest.mark.parametrize("parameters", ((), ("--ipv6",)))
@mock.patch("duffy.app.cli.uvicorn")
def test_cli_main(mock_uvicorn, parameters):
    runner = CliRunner()
    runner.invoke(main, parameters)
    mock_uvicorn.run.assert_called_once()
