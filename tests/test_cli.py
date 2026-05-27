import copy
import logging
from contextlib import nullcontext
from datetime import timedelta
from unittest import mock
from uuid import uuid4

import click
import pytest
import yaml
from click.exceptions import BadParameter
from click.testing import CliRunner

import duffy.cli
from duffy.cli import cli
from duffy.configuration import config
from duffy.exceptions import DuffyConfigurationError
from duffy.util import UNSET
from duffy.version import __version__


@pytest.fixture
def runner():
    try:
        # click < 8.2
        return CliRunner(mix_stderr=False)  # type: ignore[reportCallIssue]
    except TypeError:
        return CliRunner()


@pytest.fixture(autouse=True, scope="module")
def dont_read_system_user_config():
    with mock.patch("duffy.cli.DEFAULT_CONFIG_LOCATIONS", new=()), mock.patch(
        "duffy.cli.DEFAULT_CONFIG_PATHS", new=()
    ):
        yield


class TestIntOrNoneType:
    @pytest.mark.parametrize("value", (UNSET, 5))
    def test_convert_verbatim(self, value):
        assert duffy.cli.INT_OR_NONE.convert(value, None, None) == value

    @pytest.mark.parametrize("value", ("None", "null"))
    def test_convert_none(self, value):
        assert duffy.cli.INT_OR_NONE.convert(value, None, None) is None

    def test_convert_invalid(self):
        with pytest.raises(click.ClickException) as exc:
            duffy.cli.INT_OR_NONE.convert("hello", None, None)

        assert exc.match("'hello' is not a valid integer")

    def test_convert_valid(self):
        assert duffy.cli.INT_OR_NONE.convert("5", None, None) == 5


class TestIntervalOrNoneType:
    def test_convert_verbatim(self):
        assert duffy.cli.INTERVAL_OR_NONE.convert(UNSET, None, None) == UNSET

    @pytest.mark.parametrize("value", ("None", "null"))
    def test_convert_none(self, value):
        assert duffy.cli.INTERVAL_OR_NONE.convert(value, None, None) is None

    def test_convert_invalid(self):
        with pytest.raises(click.ClickException) as exc:
            duffy.cli.INTERVAL_OR_NONE.convert("hello", None, None)

        assert exc.match("invalid timedelta format")

    def test_convert_valid(self):
        assert duffy.cli.INTERVAL_OR_NONE.convert("5h", None, None) == timedelta(hours=5)


class TestNodesSpecType:
    def test_convert_none(self):
        assert duffy.cli.NODES_SPEC.convert(None, None, None) is None

    @pytest.mark.parametrize("testcase", ("valid", "duplicate-key", "missing-key"))
    def test_convert(self, testcase):
        if testcase == "duplicate-key":
            value = "pool=test,pool=test2,quantity=1"
            expectation = pytest.raises(BadParameter)
        elif testcase == "missing-key":
            value = "pool=test"
            expectation = pytest.raises(BadParameter)
        else:
            value = "pool=test,quantity=1"
            expectation = nullcontext()

        with expectation:
            converted = duffy.cli.NODES_SPEC.convert(value, None, None)

        if testcase == "valid":
            assert converted == {"pool": "test", "quantity": "1"}


def test_cli_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == "Duffy, version %s\n" % __version__


def test_cli_help(runner):
    """Ensure `duffy --help` works."""
    result = runner.invoke(cli, ["--help"], terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: duffy" in result.stdout


def test_cli_help_short_option(runner):
    """Ensure `duffy -h` works."""
    result = runner.invoke(cli, ["-h"], terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: duffy" in result.output


@pytest.mark.parametrize("subcommand", ["config", "migration", "admin", "client"])
def test_subcommand_help_options(runner, subcommand):
    """Ensure both -h and --help work for all CLI subgroups."""
    # Test --help
    result = runner.invoke(cli, [subcommand, "--help"], terminal_width=80)
    assert result.exit_code == 0
    assert f"Usage: duffy {subcommand}" in result.output

    # Test -h
    result = runner.invoke(cli, [subcommand, "-h"], terminal_width=80)
    assert result.exit_code == 0
    assert f"Usage: duffy {subcommand}" in result.output


def test_cli_suggestion(runner):
    result = runner.invoke(cli, ["--helo"])
    assert result.exit_code == 2
    assert any(
        error_string in result.stderr
        for error_string in (
            "Error: No such option: --helo",  # click < 8.4
            "Error: No such option '--helo'.",  # click >= 8.4
        )
    )


def test_cli_missing_config(tmp_path, runner):
    missing_config_file = tmp_path / "missing_duffy_config.yaml"
    result = runner.invoke(cli, [f"--config={missing_config_file.absolute()}"])
    assert result.exit_code != 0


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("config_empty", (False, True))
def test_config_check(config_empty, duffy_config_files, runner, tmp_path):
    (config_file,) = duffy_config_files

    if config_empty:
        # Don't overwrite example configuration
        config_file = tmp_path / "duffy-empty-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump({}, fp)

    result = runner.invoke(cli, ["--config", str(config_file), "config", "check"])

    if config_empty:
        assert result.exit_code == 0
        assert "Configuration is empty" in result.stdout
    else:
        assert result.exit_code == 0
        assert "OK" in result.stdout
        assert "Validated configuration subkeys:" in result.stdout


@pytest.mark.duffy_config(example_config=True)
def test_config_dump(runner):
    result = runner.invoke(cli, ["config", "dump"])
    dumped_config = yaml.safe_load(result.stdout)
    assert dumped_config == config


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("testcase", ("normal", "test-data", "config-error", "missing-modules"))
@mock.patch("duffy.cli.setup_db_test_data")
@mock.patch("duffy.cli.setup_db_schema")
def test_setup_db(
    setup_db_schema, setup_db_test_data, testcase, duffy_config_files, runner, caplog
):
    (config_file,) = duffy_config_files

    if "config-error" in testcase:
        setup_db_schema.side_effect = DuffyConfigurationError("database")

    args = [f"--config={config_file.absolute()}", "setup-db"]

    if "test-data" in testcase:
        args.append("--test-data")

    if "missing-modules" in testcase:
        duffy.cli.setup_db_schema = None

    result = runner.invoke(cli, args)

    if "config-error" not in testcase and "missing-modules" not in testcase:
        setup_db_schema.assert_called_once_with()
        assert result.exit_code == 0
        if testcase == "test-data":
            setup_db_test_data.assert_called_once_with()
    else:
        assert result.exit_code != 0
        if "config-error" in testcase:
            setup_db_schema.assert_called_once_with()
            assert "Configuration key missing or wrong: database" in caplog.messages
        else:
            assert "Please install the duffy[database] extra" in result.stderr


@duffy.cli.migration.command("test")
def _test_migration():
    pass


@pytest.mark.duffy_config(example_config=True)
@mock.patch("duffy.cli.alembic_migration")
class TestMigrationCLI:
    def test_migration_group_bailout(self, alembic_migration, runner, duffy_config_files):
        (config_file,) = duffy_config_files

        duffy.cli.alembic_migration = None

        parameters = [f"--config={config_file.absolute()}", "migration", "test"]

        result = runner.invoke(cli, parameters)

        assert "Please install the duffy[database] extra" in result.stderr

    @pytest.mark.parametrize("testcase", ("normal", "autogenerate", "missing-comment"))
    def test_migration_create(self, alembic_migration, testcase, runner):
        comment = "A comment"
        args = ["migration", "create"]
        if testcase == "autogenerate":
            args.append("--autogenerate")
        if testcase != "missing-comment":
            args.extend(comment.split())

        result = runner.invoke(cli, args)

        if testcase == "missing-comment":
            assert result.exit_code != 0
        else:
            assert result.exit_code == 0
            alembic_migration.create.assert_called_once_with(
                comment=comment, autogenerate=(testcase == "autogenerate")
            )

    def test_migration_db_version(self, alembic_migration, runner):
        result = runner.invoke(cli, ["migration", "db-version"])
        assert result.exit_code == 0
        alembic_migration.db_version.assert_called_once_with()

    @pytest.mark.parametrize("subcommand", ("upgrade", "downgrade"))
    def test_migration_upgrade_downgrade(self, alembic_migration, subcommand, runner):
        result = runner.invoke(cli, ["migration", subcommand, "BOO"])
        assert result.exit_code == 0
        getattr(alembic_migration, subcommand).assert_called_once_with("BOO")


@pytest.mark.parametrize(
    "config_error, shell_type",
    [(False, st) for st in (None, "python", "ipython", "bad shell type")] + [(True, None)],
)
@pytest.mark.duffy_config(example_config=True)
@mock.patch("duffy.shell.embed_shell")
@mock.patch("duffy.database.init_model")
def test_dev_shell(
    init_model, embed_shell, runner, duffy_config_files, config_error, shell_type, tmp_path
):
    # Ensure it's only one config file.
    (config_file,) = duffy_config_files

    _shell_type = shell_type or ""

    if config_error:
        modified_config = copy.deepcopy(config)
        del modified_config["database"]
        config_file = tmp_path / "duffy-broken-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump(modified_config, fp)

    args = [f"--config={config_file.absolute()}", "dev-shell"]

    if shell_type:
        args.append(f"--shell-type={shell_type}")

    if config_error:
        init_model.side_effect = DuffyConfigurationError("database")

    # Act as if IPython is always available, i.e. don't auto-detect the allowed values for
    # the --shell-type option.

    # First, dig out the relevant click.Option object, ...
    shell_type_option = [o for o in cli.commands["dev-shell"].params if o.name == "shell_type"][0]
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


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("worker_available", (True, False))
def test_worker(worker_available, duffy_config_files, runner):
    (config_file,) = duffy_config_files

    with mock.patch.object(duffy.cli, "start_worker") as start_worker:
        if not worker_available:
            duffy.cli.start_worker = None
        result = runner.invoke(
            cli, [f"--config={config_file.absolute()}", "worker", "a", "-b", "c", "--dee"]
        )

    if worker_available:
        assert result.exit_code == 0
        start_worker.assert_called_once_with(worker_args=("a", "-b", "c", "--dee"))
    else:
        assert result.exit_code != 0
        assert "Please install the duffy[tasks] extra for this command" in result.stderr


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize(
    "testcase",
    (
        "default",
        "with-options",
        "without-logging-config",
        "missing-uvicorn-module",
        "missing-app-extra",
    ),
)
@mock.patch("duffy.cli.logging")
@mock.patch("duffy.cli.uvicorn.run")
def test_serve(uvicorn_run, logging, testcase, runner, duffy_config_files, tmp_path):
    (config_file,) = duffy_config_files

    if "without-logging-config" in testcase:
        modified_config = copy.deepcopy(config)
        del modified_config["app"]["logging"]
        config_file = tmp_path / "duffy-test-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump(modified_config, fp)

    if "missing-uvicorn-module" in testcase:
        ctxmgr = mock.patch.object(duffy.cli, "uvicorn", None)
    elif "missing-app-extra" in testcase:
        ctxmgr = mock.patch.object(duffy.cli, "RequestIdFilter", None)
    else:
        ctxmgr = nullcontext()

    parameters = (f"--config={config_file.absolute()}", "serve")

    if "with-options" in testcase:
        parameters = ("--loglevel=info",) + parameters + ("--host=127.0.0.1", "--port=8080")

    with ctxmgr:
        result = runner.invoke(cli, parameters)

    if "missing-uvicorn-module" not in testcase:
        assert result.exit_code == 0
        uvicorn_run.assert_called_once()
        if "without-logging-config" in testcase:
            logging.config.dictConfig.assert_not_called()
        else:
            logging.config.dictConfig.assert_called_once_with(config["metaclient"]["logging"])
    else:
        assert result.exit_code != 0
        assert "Please install the duffy[app] extra" in result.stderr


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize(
    "testcase",
    (
        "default",
        "with-options",
        "without-logging-config",
        "missing-uvicorn-module",
        "missing-app-extra",
    ),
)
@mock.patch("duffy.cli.logging")
@mock.patch("duffy.cli.uvicorn.run")
def test_serve_legacy(uvicorn_run, logging, testcase, runner, duffy_config_files, tmp_path):
    (config_file,) = duffy_config_files

    if "without-logging-config" in testcase:
        modified_config = copy.deepcopy(config)
        del modified_config["metaclient"]["logging"]
        config_file = tmp_path / "duffy-test-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump(modified_config, fp)

    if "missing-uvicorn-module" in testcase:
        ctxmgr = mock.patch.object(duffy.cli, "uvicorn", None)
    elif "missing-app-extra" in testcase:
        ctxmgr = mock.patch.object(duffy.cli, "RequestIdFilter", None)
    else:
        ctxmgr = nullcontext()

    parameters = (f"--config={config_file.absolute()}", "serve-legacy")

    if "with-options" in testcase:
        parameters = (
            ("--loglevel=info",)
            + parameters
            + ("--host=127.0.0.1", "--port=9090", "--dest=http://127.0.0.1:8080")
        )

    with ctxmgr:
        result = runner.invoke(cli, parameters)

    if "missing-uvicorn-module" not in testcase:
        assert result.exit_code == 0
        uvicorn_run.assert_called_once()
        if "without-logging-config" in testcase:
            logging.config.dictConfig.assert_not_called()
        else:
            logging.config.dictConfig.assert_called_once_with(config["metaclient"]["logging"])
    else:
        assert result.exit_code != 0
        assert "Please install the duffy[legacy] extra for this command" in result.stderr


@duffy.cli.admin_group.command("test")
def _test_admin():
    pass


@pytest.mark.duffy_config(example_config=True)
@mock.patch.object(duffy.cli.admin.AdminContext, "create_for_cli")
class TestAdminCLI:
    @mock.patch("duffy.cli.admin", None)
    def test_admin_group_bailout(self, create_for_cli, runner, duffy_config_files):
        (config_file,) = duffy_config_files

        parameters = [f"--config={config_file.absolute()}", "admin", "test"]

        result = runner.invoke(cli, parameters)

        assert "Please install the duffy[admin] extra" in result.stderr

    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_list_tenants(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        success = "failure" not in testcase

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if success:
            result_tenant_1 = mock.MagicMock()
            result_tenant_1.name = "tenant-1-name"
            result_tenant_2 = mock.MagicMock()
            result_tenant_2.name = "tenant-2-name"
            result_tenant_2.active = False
            admin_ctx.list_tenants.return_value = {"tenants": [result_tenant_1, result_tenant_2]}
        else:
            admin_ctx.list_tenants.return_value = {"error": {"detail": "BOOM"}}

        parameters = (f"--config={config_file.absolute()}", "admin", "list-tenants")

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.strip() == "OK: tenant-1-name"
        else:
            assert result.exit_code == 1
            assert result.stderr.strip() == "ERROR: couldn't list tenants\nERROR DETAIL: BOOM"

    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_show_tenant(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        success = "failure" not in testcase

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if success:
            result_tenant = mock.MagicMock()
            admin_ctx.show_tenant.return_value = {"tenant": result_tenant}
        else:
            admin_ctx.show_tenant.return_value = {"error": {"detail": "BAR"}}

        parameters = (f"--config={config_file.absolute()}", "admin", "show-tenant", "tenant-name")

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stderr.strip() == "ERROR: tenant-name\nERROR DETAIL: BAR"

    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_create_tenant(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if testcase == "failure":
            admin_ctx.create_tenant.return_value = {"error": {"detail": "FOO"}}
        else:
            result_tenant = mock.MagicMock()
            result_tenant.api_key = "APIKEY"
            admin_ctx.create_tenant.return_value = {"tenant": result_tenant}

        parameters = (
            f"--config={config_file.absolute()}",
            "admin",
            "create-tenant",
            "tenant-name",
            "# no SSH key",
        )

        result = runner.invoke(cli, parameters)

        if testcase == "success":
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stderr.strip() == "ERROR: tenant-name\nERROR DETAIL: FOO"

    @pytest.mark.parametrize("testcase", ("retire", "unretire", "failure"))
    def test_retire_unretire_tenant(
        self, create_for_cli, testcase, runner, duffy_config_files, caplog
    ):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        retire = "unretire" not in testcase
        success = "failure" not in testcase

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if success:
            result_tenant = mock.MagicMock()
            result_tenant.active = not retire
            admin_ctx.retire_unretire_tenant.return_value = {"tenant": result_tenant}
        else:
            admin_ctx.retire_unretire_tenant.return_value = {"error": {"detail": "BAR"}}

        parameters = (
            f"--config={config_file.absolute()}",
            "admin",
            "retire-tenant",
            "tenant-name",
            "--retire" if retire else "--unretire",
        )

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stderr.strip() == "ERROR: tenant-name\nERROR DETAIL: BAR"

    @pytest.mark.parametrize(
        "testcase",
        (
            "success",
            "success-update-quota",
            "success-unset-quota",
            "success-update-session-lifetime",
            "success-unset-session-lifetime",
            "success-update-session-lifetime-max",
            "success-unset-session-lifetime-max",
            "failure",
            "missing-arguments",
        ),
    )
    def test_update_tenant(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        new_ssh_key = "# new ssh key"
        new_api_key = "# new API key"
        node_quota = session_lifetime = session_lifetime_max = object()

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if testcase == "failure":
            admin_ctx.update_tenant.return_value = {"error": {"detail": "BLOOP"}}
        else:
            result_tenant = mock.MagicMock()
            result_tenant.ssh_key = new_ssh_key
            result_tenant.api_key = new_api_key
            if "update-quota" in testcase:
                result_tenant.effective_quota = result_tenant.node_quota = node_quota = 5
            else:
                result_tenant.node_quota = node_quota = None
                result_tenant.effective_quota = 10

            if "update-session-lifetime-max" in testcase:
                session_lifetime_max = "7200"
                result_tenant.session_lifetime_max = timedelta(hours=2)
                result_tenant.effective_session_lifetime_max = result_tenant.session_lifetime_max
            else:
                result_tenant.session_lifetime_max = session_lifetime_max = None
                result_tenant.effective_session_lifetime_max = timedelta(hours=12)

                if "update-session-lifetime" in testcase:
                    session_lifetime = "1h"
                    result_tenant.session_lifetime = timedelta(hours=1)
                    result_tenant.effective_session_lifetime = result_tenant.session_lifetime
                else:
                    result_tenant.session_lifetime = session_lifetime = None
                    result_tenant.effective_session_lifetime = timedelta(hours=6)

            admin_ctx.update_tenant.return_value = {"tenant": result_tenant}

        parameters = (f"--config={config_file.absolute()}", "admin", "update-tenant", "tenant-name")

        if testcase != "missing-arguments":
            parameters += ("--ssh-key", new_ssh_key, "--api-key", new_api_key)
            if node_quota is None or isinstance(node_quota, int):
                parameters += ("--node-quota", str(node_quota))
            if session_lifetime is None or isinstance(session_lifetime, timedelta):
                parameters += ("--session-lifetime", str(session_lifetime))
            if session_lifetime_max is None or isinstance(session_lifetime_max, timedelta):
                parameters += ("--session-lifetime-max", str(session_lifetime_max))

        result = runner.invoke(cli, parameters)

        if "success" in testcase:
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            if testcase == "failure":
                assert result.stderr.strip() == "ERROR: tenant-name\nERROR DETAIL: BLOOP"
            else:
                assert result.stderr.strip() == (
                    "ERROR: Either --ssh-key, --api-key, --node-quota, --session-lifetime or"
                    " --session-lifetime-max must be set."
                )


@duffy.cli.client.command("test")
def _test_client():
    pass


@pytest.mark.duffy_config(example_config=True)
@mock.patch("duffy.cli.DuffyFormatter")
@mock.patch("duffy.cli.DuffyClient")
class TestClientCLI:
    @pytest.mark.parametrize("testcase", ("defaults", "format", "options", "missing-modules"))
    def test_client_group(self, DuffyClient, DuffyFormatter, testcase, runner, duffy_config_files):
        (config_file,) = duffy_config_files

        url = auth_name = auth_key = None
        format = "json"

        parameters = [f"--config={config_file.absolute()}", "client"]

        if testcase == "format":
            format = "flat"
            parameters.append("--format=flat")

        if testcase == "options":
            url = "http://localhost:9876"
            auth_name = "boo"
            auth_key = str(uuid4())
            parameters.extend(
                [f"--url={url}", f"--auth-name={auth_name}", f"--auth-key={auth_key}"]
            )

        parameters.append("test")

        duffy_client_sentinel = object()
        duffy_formatter_sentinel = object()

        if "missing-modules" in testcase:
            duffy.cli.DuffyClient = duffy.cli.DuffyFormatter = None
        else:
            DuffyClient.return_value = duffy_client_sentinel
            DuffyFormatter.new_for_format.return_value = duffy_formatter_sentinel

        obj = {}
        result = runner.invoke(cli, parameters, obj=obj)

        if "missing-modules" not in testcase:
            assert result.exit_code == 0
            assert obj["client"] is duffy_client_sentinel
            assert obj["formatter"] is duffy_formatter_sentinel
            DuffyClient.assert_called_once_with(url=url, auth_name=auth_name, auth_key=auth_key)
            DuffyFormatter.new_for_format.assert_called_once_with(format)
        else:
            assert result.exit_code != 0
            assert "Please install the duffy[client] extra for this command" in result.stderr

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_list_sessions(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        sessions_sentinel = {"sessions": [{"id": 1, "name": "test"}]}
        client.list_sessions.return_value = sessions_sentinel
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatted_result_sentinel = "formatted_sessions"
        formatter.format.return_value = formatted_result_sentinel

        parameters = [f"--config={config_file.absolute()}", "client", "list-sessions"]

        runner.invoke(cli, parameters)

        client.list_sessions.assert_called_once_with()
        formatter.format.assert_called_once_with(sessions_sentinel)

        click_echo.assert_called_once_with(formatted_result_sentinel, nl=True)
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_list_sessions_error(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "API error"}}
        client.list_sessions.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: API error"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [f"--config={config_file.absolute()}", "client", "list-sessions"]

        runner.invoke(cli, parameters)

        client.list_sessions.assert_called_once_with()
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: API error", err=True)
        sys_exit.assert_called_once_with(1)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_show_session(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.show_session.return_value = session_sentinel = {
            "session_id": 123,
            "status": "active",
        }
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = "Session 123: active"

        parameters = [f"--config={config_file.absolute()}", "client", "show-session", "15"]

        runner.invoke(cli, parameters)

        client.show_session.assert_called_once_with(15)
        formatter.format.assert_called_once_with(session_sentinel)

        click_echo.assert_called_once_with(result_sentinel)
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_show_session_error(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "Session not found"}}
        client.show_session.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: Session not found"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [f"--config={config_file.absolute()}", "client", "show-session", "15"]

        runner.invoke(cli, parameters)

        client.show_session.assert_called_once_with(15)
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: Session not found", err=True)
        sys_exit.assert_called_once_with(1)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.request_session.return_value = session_sentinel = {"session_id": 123}
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = "Session created: 123"

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "pool=pool,quantity=1",
            "pool=pool2,quantity=2",
        ]

        runner.invoke(cli, parameters)

        client.request_session.assert_called_once_with(
            ({"pool": "pool", "quantity": "1"}, {"pool": "pool2", "quantity": "2"})
        )
        formatter.format.assert_called_once_with(session_sentinel)

        click_echo.assert_called_once_with(result_sentinel)
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session_error_no_retry(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "No nodes available"}}
        client.request_session.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: No nodes available"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "pool=pool,quantity=1",
        ]

        runner.invoke(cli, parameters)

        client.request_session.assert_called_once_with(({"pool": "pool", "quantity": "1"},))
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: No nodes available", err=True)
        sys_exit.assert_called_once_with(1)

    @mock.patch("duffy.cli.time.sleep")
    @mock.patch("duffy.cli.time.time")
    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session_retry_success(
        self,
        sys_exit,
        click_echo,
        time_time,
        time_sleep,
        DuffyClient,
        DuffyFormatter,
        runner,
        duffy_config_files,
    ):
        (config_file,) = duffy_config_files

        # Mock time.time() to simulate passage of time
        time_time.side_effect = [0, 30, 90]  # Start, after first failure, after success

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "No nodes available"}}
        success_result = {"session_id": 123}
        # First call fails, second call succeeds
        client.request_session.side_effect = [error_result, success_result]

        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()
        formatter.format.return_value = "Session created successfully"

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "--retry",
            "--timeout=5",
            "--retry-interval=45",
            "pool=pool,quantity=1",
        ]

        runner.invoke(cli, parameters)

        # Should be called twice: once fails, once succeeds
        assert client.request_session.call_count == 2

        # Should sleep once between attempts
        time_sleep.assert_called_once_with(45)

        # Should output success message and result
        assert any("Success after 2 attempts!" in str(call) for call in click_echo.call_args_list)
        click_echo.assert_any_call("Session created successfully")

        sys_exit.assert_called_once_with(0)

    @mock.patch("duffy.cli.time.sleep")
    @mock.patch("duffy.cli.time.time")
    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session_retry_timeout(
        self,
        sys_exit,
        click_echo,
        time_time,
        time_sleep,
        DuffyClient,
        DuffyFormatter,
        runner,
        duffy_config_files,
    ):
        (config_file,) = duffy_config_files

        # Mock time.time() to simulate timeout after 2 minutes
        time_time.side_effect = [0, 45, 90, 135, 300]  # Start, after each attempt

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "No nodes available"}}
        client.request_session.return_value = error_result

        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()
        formatter.format.return_value = "ERROR: No nodes available"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "--retry",
            "--timeout=2",  # 2 minutes timeout
            "--retry-interval=45",
            "pool=pool,quantity=1",
        ]

        result = runner.invoke(cli, parameters)

        # Should attempt multiple times until timeout
        assert client.request_session.call_count >= 2

        # Should output timeout message
        assert any(
            "Timeout reached after 2 minutes" in str(call) for call in click_echo.call_args_list
        )

        sys_exit.assert_called_once_with(1)
        assert result.exit_code == 1

    @mock.patch("duffy.cli.time.sleep")
    @mock.patch("duffy.cli.time.time")
    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session_retry_progress_reporting(
        self,
        sys_exit,
        click_echo,
        time_time,
        time_sleep,
        DuffyClient,
        DuffyFormatter,
        runner,
        duffy_config_files,
    ):
        (config_file,) = duffy_config_files

        # Mock time.time() to simulate 6 attempts (to trigger progress reporting every 5)
        time_time.side_effect = [0, 45, 90, 135, 180, 225, 270, 315, 360]

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "No nodes available"}}
        success_result = {"session_id": 123}
        # Fail 5 times, then succeed on 6th attempt
        client.request_session.side_effect = [error_result] * 5 + [success_result]

        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()
        formatter.format.return_value = "Session created successfully"

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "--retry",
            "--timeout=10",  # 10 minutes timeout
            "--retry-interval=45",
            "pool=pool,quantity=1",
        ]

        runner.invoke(cli, parameters)

        # Should be called 6 times: 5 failures + 1 success
        assert client.request_session.call_count == 6

        # Should output progress message after 5 attempts
        assert any("Still trying... (attempt 5," in str(call) for call in click_echo.call_args_list)

        # Should output success message
        assert any("Success after 6 attempts!" in str(call) for call in click_echo.call_args_list)

        sys_exit.assert_called_once_with(0)

    @mock.patch("duffy.cli.time.sleep")
    @mock.patch("duffy.cli.time.time")
    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_request_session_retry_timeout_with_zero_sleep(
        self,
        sys_exit,
        click_echo,
        time_time,
        time_sleep,
        DuffyClient,
        DuffyFormatter,
        runner,
        duffy_config_files,
    ):
        """Test timeout when sleep_duration becomes <= 0."""
        (config_file,) = duffy_config_files

        # Mock time.time() to simulate scenario where retry_interval=0 triggers sleep_duration <= 0
        # With retry_interval=0, sleep_duration = min(0, remaining_time) = 0
        # This will trigger the second timeout condition (lines 784-786)
        time_time.side_effect = [0, 30]  # First attempt, then immediate retry due to interval=0

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "No nodes available"}}
        client.request_session.return_value = error_result

        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()
        formatter.format.return_value = "ERROR: No nodes available"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [
            f"--config={config_file.absolute()}",
            "client",
            "request-session",
            "--retry",
            "--timeout=1",  # 1 minute timeout
            "--retry-interval=0",
            "pool=pool,quantity=1",
        ]

        result = runner.invoke(cli, parameters)

        # Should attempt only once, then sleep_duration <= 0 triggers immediate timeout
        assert client.request_session.call_count == 1

        # Should not call sleep when sleep_duration <= 0
        time_sleep.assert_not_called()

        # Should output timeout message for sleep_duration <= 0 case
        assert any(
            "Timeout reached after 1 minutes" in str(call) for call in click_echo.call_args_list
        )

        sys_exit.assert_called_once_with(1)
        assert result.exit_code == 1

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_retire_session(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.retire_session.return_value = session_sentinel = {
            "session_id": 51,
            "status": "retired",
        }
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = "Session 51 retired successfully"

        parameters = [f"--config={config_file.absolute()}", "client", "retire-session", "51"]

        runner.invoke(cli, parameters)

        client.retire_session.assert_called_once_with(51)
        formatter.format.assert_called_once_with(session_sentinel)

        click_echo.assert_called_once_with(result_sentinel)
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_retire_session_error(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "Session not found or already retired"}}
        client.retire_session.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: Session not found or already retired"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [f"--config={config_file.absolute()}", "client", "retire-session", "51"]

        runner.invoke(cli, parameters)

        client.retire_session.assert_called_once_with(51)
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: Session not found or already retired", err=True)
        sys_exit.assert_called_once_with(1)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_list_pools(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.list_pools.return_value = pools_sentinel = [{"name": "pool1"}, {"name": "pool2"}]
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = formatted_result_sentinel = "pool1\npool2"

        parameters = [f"--config={config_file.absolute()}", "client", "list-pools"]

        runner.invoke(cli, parameters)

        client.list_pools.assert_called_once_with()
        formatter.format.assert_called_once_with(pools_sentinel)

        click_echo.assert_called_once_with(
            formatted_result_sentinel, nl=bool(formatted_result_sentinel)
        )
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_list_pools_error(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "Failed to retrieve pools"}}
        client.list_pools.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: Failed to retrieve pools"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [f"--config={config_file.absolute()}", "client", "list-pools"]

        runner.invoke(cli, parameters)

        client.list_pools.assert_called_once_with()
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: Failed to retrieve pools", err=True)
        sys_exit.assert_called_once_with(1)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_show_pool(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.show_pool.return_value = pool_sentinel = {"name": "lagoon", "nodes": 5}
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = formatted_result_sentinel = "Pool: lagoon (5 nodes)"

        parameters = [f"--config={config_file.absolute()}", "client", "show-pool", "lagoon"]

        runner.invoke(cli, parameters)

        client.show_pool.assert_called_once_with("lagoon")
        formatter.format.assert_called_once_with(pool_sentinel)

        click_echo.assert_called_once_with(formatted_result_sentinel)
        sys_exit.assert_called_once_with(0)

    @mock.patch("click.echo")
    @mock.patch("duffy.cli.sys.exit")
    def test_show_pool_error(
        self, sys_exit, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        error_result = {"error": {"detail": "Pool not found"}}
        client.show_pool.return_value = error_result
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = "ERROR: Pool not found"
        # Configure sys_exit to raise SystemExit with proper exit code
        sys_exit.side_effect = lambda code: exec("raise SystemExit(code)")

        parameters = [f"--config={config_file.absolute()}", "client", "show-pool", "lagoon"]

        runner.invoke(cli, parameters)

        client.show_pool.assert_called_once_with("lagoon")
        formatter.format.assert_called_with(error_result)

        # Verify error is output to stderr and exit(1) is called
        click_echo.assert_called_with("ERROR: Pool not found", err=True)
        sys_exit.assert_called_once_with(1)
