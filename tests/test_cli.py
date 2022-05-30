import copy
import logging
from datetime import timedelta
from tempfile import TemporaryDirectory
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

from .util import noop_context


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True, scope="module")
def dont_read_etc_duffy():
    # Modify the default value for `--config`. For that, find the right parameter object on the
    # (click-wrapped) cli() function, then mock its default below.
    for param in cli.params:
        if param.name == "config":
            break
    else:  # Oops, didn't find right param object. This shouldn't happen!
        raise RuntimeError("Can't find right parameter object for `--config`.")

    with TemporaryDirectory(prefix="dont_read_etc_duffy-") as tmpdir, mock.patch(
        "duffy.cli.DEFAULT_CONFIG_FILE", new=tmpdir
    ), mock.patch.object(param, "default", new=tmpdir):
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
            duffy.cli.INT_OR_NONE.convert("hello", "<param>", None)

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
            duffy.cli.INTERVAL_OR_NONE.convert("hello", "<param>", None)

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
            expectation = noop_context()

        with expectation:
            converted = duffy.cli.NODES_SPEC.convert(value, None, None)

        if testcase == "valid":
            assert converted == {"pool": "test", "quantity": "1"}


@pytest.mark.parametrize(
    "testcase", ("default", "default-not-found", "other-not-found", "default-plus-one")
)
@mock.patch("duffy.cli.read_configuration")
def test_init_config(read_configuration, testcase):
    if "not-found" in testcase:
        read_configuration.side_effect = FileNotFoundError()

    if "default" in testcase:
        expectation = noop_context()
        filename = duffy.cli.DEFAULT_CONFIG_FILE
    else:
        expectation = pytest.raises(FileNotFoundError)
        filename = "boop"

    ctx = mock.MagicMock()
    ctx.obj = {}
    param = mock.MagicMock()

    with expectation:
        duffy.cli.init_config(ctx, param, filename)

    read_configuration.assert_called_once_with(filename, clear=True, validate=False)

    if "plus-one" in testcase:
        read_configuration.reset_mock(return_value=True, side_effect=True)

        duffy.cli.init_config(ctx, param, "foo")

        read_configuration.assert_called_once_with("foo", clear=False, validate=False)


def test_cli_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output == "Duffy, version %s\n" % __version__


def test_cli_help(runner):
    """Ensure `duffy --help` works."""
    result = runner.invoke(cli, ["--help"], terminal_width=80)
    assert result.exit_code == 0
    assert "Usage: duffy" in result.output


def test_cli_suggestion(runner):
    result = runner.invoke(cli, ["--helo"])
    assert result.exit_code == 2
    assert "Error: No such option: --helo" in result.output


def test_cli_missing_config(tmp_path, runner):
    missing_config_file = tmp_path / "missing_duffy_config.yaml"
    result = runner.invoke(cli, [f"--config={missing_config_file.absolute()}"])
    assert result.exit_code == 1
    assert isinstance(result.exception, FileNotFoundError)


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
        assert "Configuration is empty" in result.output
    else:
        assert result.exit_code == 0
        assert "OK" in result.output
        assert "Validated configuration subkeys:" in result.output


@pytest.mark.duffy_config(example_config=True)
def test_config_dump(runner):
    result = runner.invoke(cli, ["config", "dump"])
    dumped_config = yaml.safe_load(result.output)
    assert dumped_config == config


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("testcase", ("normal", "test-data", "config-error"))
@mock.patch("duffy.cli.setup_db_test_data")
@mock.patch("duffy.cli.setup_db_schema")
def test_setup_db(
    setup_db_schema, setup_db_test_data, testcase, duffy_config_files, runner, caplog
):
    (config_file,) = duffy_config_files
    if testcase == "config-error":
        setup_db_schema.side_effect = DuffyConfigurationError("database")
    args = [f"--config={config_file.absolute()}", "setup-db"]
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


@pytest.mark.parametrize("testcase", ("normal", "autogenerate", "missing-comment"))
@mock.patch("duffy.cli.alembic_migration")
def test_migration_create(alembic_migration, testcase, runner):
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


@mock.patch("duffy.cli.alembic_migration")
def test_migration_db_version(alembic_migration, runner):
    result = runner.invoke(cli, ["migration", "db-version"])
    assert result.exit_code == 0
    alembic_migration.db_version.assert_called_once_with()


@pytest.mark.parametrize("subcommand", ("upgrade", "downgrade"))
@mock.patch("duffy.cli.alembic_migration")
def test_migration_upgrade_downgrade(alembic_migration, subcommand, runner):
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
@mock.patch("duffy.cli.start_worker")
def test_worker(start_worker, duffy_config_files, runner):
    (config_file,) = duffy_config_files
    result = runner.invoke(
        cli, [f"--config={config_file.absolute()}", "worker", "a", "-b", "c", "--dee"]
    )

    assert result.exit_code == 0
    start_worker.assert_called_once_with(worker_args=("a", "-b", "c", "--dee"))


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("testcase", ("default", "with-options", "missing-logging-config"))
@mock.patch("duffy.cli.uvicorn.run")
def test_serve(uvicorn_run, testcase, runner, duffy_config_files, tmp_path):
    (config_file,) = duffy_config_files

    if testcase == "missing-logging-config":
        modified_config = copy.deepcopy(config)
        del modified_config["app"]["logging"]
        config_file = tmp_path / "duffy-broken-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump(modified_config, fp)

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

    result = runner.invoke(cli, parameters)
    assert result.exit_code == 0
    uvicorn_run.assert_called_once()


@pytest.mark.duffy_config(example_config=True)
@pytest.mark.parametrize("testcase", ("default", "with-options", "missing-logging-config"))
@mock.patch("duffy.cli.uvicorn.run")
def test_serve_legacy(uvicorn_run, testcase, runner, duffy_config_files, tmp_path):
    (config_file,) = duffy_config_files

    if testcase == "missing-logging-config":
        modified_config = copy.deepcopy(config)
        del modified_config["metaclient"]["logging"]
        config_file = tmp_path / "duffy-broken-config.yaml"
        with config_file.open("w") as fp:
            yaml.dump(modified_config, fp)

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

    result = runner.invoke(cli, parameters)
    assert result.exit_code == 0
    uvicorn_run.assert_called_once()


@pytest.mark.duffy_config(example_config=True)
@mock.patch.object(duffy.cli.admin.AdminContext, "create_for_cli")
class TestAdminCLI:
    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_tenant_list(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
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

        parameters = (f"--config={config_file.absolute()}", "tenant", "list")

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.strip() == "OK: tenant-1-name"
        else:
            assert result.exit_code == 1
            assert result.stdout.strip() == "ERROR: couldn't list tenants\nERROR DETAIL: BOOM"

    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_tenant_show(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
        caplog.set_level(logging.DEBUG)
        (config_file,) = duffy_config_files

        success = "failure" not in testcase

        create_for_cli.return_value = admin_ctx = mock.MagicMock()

        if success:
            result_tenant = mock.MagicMock()
            admin_ctx.show_tenant.return_value = {"tenant": result_tenant}
        else:
            admin_ctx.show_tenant.return_value = {"error": {"detail": "BAR"}}

        parameters = (f"--config={config_file.absolute()}", "tenant", "show", "tenant-name")

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stdout.strip() == "ERROR: tenant-name\nERROR DETAIL: BAR"

    @pytest.mark.parametrize("testcase", ("success", "failure"))
    def test_tenant_create(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
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
            "tenant",
            "create",
            "tenant-name",
            "# no SSH key",
        )

        result = runner.invoke(cli, parameters)

        if testcase == "success":
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stdout.strip() == "ERROR: tenant-name\nERROR DETAIL: FOO"

    @pytest.mark.parametrize("testcase", ("retire", "unretire", "failure"))
    def test_tenant_retire_unretire(
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
            "tenant",
            "retire",
            "tenant-name",
            "--retire" if retire else "--unretire",
        )

        result = runner.invoke(cli, parameters)

        if success:
            assert result.exit_code == 0
            assert result.stdout.startswith("OK: tenant-name:")
        else:
            assert result.exit_code == 1
            assert result.stdout.strip() == "ERROR: tenant-name\nERROR DETAIL: BAR"

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
    def test_tenant_update(self, create_for_cli, testcase, runner, duffy_config_files, caplog):
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

        parameters = (f"--config={config_file.absolute()}", "tenant", "update", "tenant-name")

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
            assert result.exit_code == 1
            if testcase == "failure":
                assert result.stdout.strip() == "ERROR: tenant-name\nERROR DETAIL: BLOOP"
            else:
                assert result.stdout.strip() == (
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
    @pytest.mark.parametrize("testcase", ("defaults", "format", "options"))
    def test_client_session(
        self, DuffyClient, DuffyFormatter, testcase, runner, duffy_config_files
    ):
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

        DuffyClient.return_value = duffy_client_sentinel = object()
        DuffyFormatter.new_for_format.return_value = duffy_formatter_sentinel = object()

        obj = {}
        runner.invoke(cli, parameters, obj=obj)

        assert obj["client"] is duffy_client_sentinel
        assert obj["formatter"] is duffy_formatter_sentinel
        DuffyClient.assert_called_once_with(url=url, auth_name=auth_name, auth_key=auth_key)
        DuffyFormatter.new_for_format.assert_called_once_with(format)

    @pytest.mark.parametrize("testcase", ("no-results", "one-result"))
    @mock.patch.object(duffy.cli.click, "echo")
    def test_list_sessions(
        self, click_echo, DuffyClient, DuffyFormatter, testcase, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.list_sessions.return_value = sessions_sentinel = object()
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        if testcase == "no-results":
            formatter.format.return_value = []
        else:
            formatter.format.return_value = results_sentinel = [object()]

        parameters = [f"--config={config_file.absolute()}", "client", "list-sessions"]

        runner.invoke(cli, parameters)

        client.list_sessions.assert_called_once_with()
        formatter.format.assert_called_once_with(sessions_sentinel)

        if testcase == "no-results":
            click_echo.assert_not_called()
        else:
            click_echo.assert_called_once_with(results_sentinel)

    @mock.patch.object(duffy.cli.click, "echo")
    def test_show_session(
        self, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.show_session.return_value = session_sentinel = object()
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = object()

        parameters = [f"--config={config_file.absolute()}", "client", "show-session", "15"]

        runner.invoke(cli, parameters)

        client.show_session.assert_called_once_with(15)
        formatter.format.assert_called_once_with(session_sentinel)

        click_echo.assert_called_once_with(result_sentinel)

    @mock.patch.object(duffy.cli.click, "echo")
    def test_request_session(
        self, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.request_session.return_value = session_sentinel = object()
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = object()

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

    @mock.patch.object(duffy.cli.click, "echo")
    def test_retire_session(
        self, click_echo, DuffyClient, DuffyFormatter, runner, duffy_config_files
    ):
        (config_file,) = duffy_config_files

        DuffyClient.return_value = client = mock.MagicMock()
        client.retire_session.return_value = session_sentinel = object()
        DuffyFormatter.new_for_format.return_value = formatter = mock.MagicMock()

        formatter.format.return_value = result_sentinel = object()

        parameters = [f"--config={config_file.absolute()}", "client", "retire-session", "51"]

        runner.invoke(cli, parameters)

        client.retire_session.assert_called_once_with(51)
        formatter.format.assert_called_once_with(session_sentinel)

        click_echo.assert_called_once_with(result_sentinel)
