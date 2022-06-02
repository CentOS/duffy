import copy
import logging
import sys
from datetime import timedelta
from typing import List, Optional, Tuple, Union

import click
import uvicorn
import yaml

from . import admin, database, shell

try:
    from .client import DuffyClient, DuffyFormatter
except ImportError:  # pragma: no cover
    DuffyClient = DuffyFormatter = None
from .configuration import config, read_configuration
from .database.migrations.main import alembic_migration
from .database.setup import setup_db_schema, setup_db_test_data
from .exceptions import DuffyConfigurationError
from .misc import ConfigTimeDelta

try:
    from .tasks import start_worker
except ImportError:  # pragma: no cover
    start_worker = None
from .util import UNSET, SentinelType
from .version import __version__

DEFAULT_CONFIG_FILE = "/etc/duffy"

log = logging.getLogger(__name__)


# Custom Click parameter types


class IntOrNoneType(click.ParamType):
    name = "int_or_none"

    def convert(self, value, param, ctx):
        if value is UNSET or isinstance(value, int):
            return value

        try:
            if isinstance(value, str) and value.lower() in ("none", "null"):
                return None

            return int(value)
        except ValueError:
            self.fail(f"{value!r} is not a valid integer", param, ctx)


INT_OR_NONE = IntOrNoneType()


class IntervalOrNoneType(click.ParamType):
    name = "interval_or_none"

    def convert(self, value, param, ctx):
        if value is UNSET:
            return value

        try:
            if isinstance(value, str) and value.lower() in ("none", "null"):
                return None

            return ConfigTimeDelta.validate(value)
        except ValueError as exc:
            self.fail(exc.args[0] if exc.args else f"Can't convert value {value!r}", param, ctx)


INTERVAL_OR_NONE = IntervalOrNoneType()


class NodesSpecType(click.ParamType):
    name = "nodes_spec"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        nodes_spec = {}
        for item in value.split(","):
            key, value = item.split("=", 1)
            if key in nodes_spec:
                self.fail(f"Duplicate key: {key}")

            nodes_spec[key] = value

        if set(nodes_spec) != {"pool", "quantity"}:
            self.fail("Both `pool` and `quantity` must be set")

        return nodes_spec


NODES_SPEC = NodesSpecType()


# Global setup and CLI options


def init_config(ctx, param, filename):
    ctx.ensure_object(dict)
    try:
        read_configuration(filename, clear=ctx.obj.get("clear_config", True), validate=False)
    except FileNotFoundError:
        if filename is not DEFAULT_CONFIG_FILE:
            raise
    ctx.obj["clear_config"] = False


@click.group(name="duffy")
@click.option(
    "-c",
    "--config",
    type=click.Path(),
    default=DEFAULT_CONFIG_FILE,
    callback=init_config,
    is_eager=True,
    expose_value=False,
    help="Read configuration from the specified YAML files or directories.",
    show_default=True,
    metavar="FILE_OR_DIR",
)
@click.version_option(version=__version__, prog_name="Duffy")
def cli():
    read_configuration(clear=False, validate=True)


# Check & dump configuration


@cli.group(name="config")
def config_subcmd():
    """Check and dump configuration."""


@config_subcmd.command(name="check")
def config_check():
    """Validate configuration structure.

    This checks if configuration subkeys conform to the expected format.
    However, it doesn't check if the sub-keys necessary to run a certain
    subcommand exist.
    """
    if not config:
        click.echo("Configuration is empty.")
    else:
        click.echo(f"OK.\nValidated configuration subkeys: {', '.join(config)}")


@config_subcmd.command("dump")
def config_dump():
    """Dump merged configuration."""
    yaml.safe_dump(config, sys.stdout)


# Set up the database tables


@cli.command()
@click.option(
    "--test-data/--no-test-data", default=False, help="Initialized database with test data."
)
def setup_db(test_data):
    """Create tables from the database model."""
    try:
        setup_db_schema()
        if test_data:
            database.init_model()
            setup_db_test_data()
    except DuffyConfigurationError as exc:
        log.error("Configuration key missing or wrong: %s", exc.args[0])
        sys.exit(1)


# Handle database migrations


@cli.group()
def migration():
    """Handle database migrations."""
    pass


@migration.command("create")
@click.option(
    "--autogenerate/--no-autogenerate",
    default=False,
    help="Autogenerate migration script skeleton (needs to be reviewed/edited).",
)
@click.argument("comment", nargs=-1, required=True)
def migration_create(autogenerate, comment):
    """Create a new database schema migration."""
    alembic_migration.create(comment=" ".join(comment), autogenerate=autogenerate)


@migration.command("db-version")
def migration_db_version():
    """Show the current version of the database schema."""
    alembic_migration.db_version()


@migration.command("upgrade")
@click.argument("version", default="head")
def migration_upgrade(version):
    """Upgrade the database schema."""
    alembic_migration.upgrade(version)


@migration.command("downgrade")
@click.argument("version", default="-1")
def migration_downgrade(version):
    """Downgrade the database schema."""
    alembic_migration.downgrade(version)


# Interactive development/debugging shell


@cli.command(name="dev-shell")
@click.option(
    "-t",
    "--shell-type",
    type=click.Choice(shell.get_available_shells(), case_sensitive=False),
    help="Type of interactive shell to use.",
    default=None,
)
def dev_shell(shell_type: str):
    """Run an interactive shell."""
    try:
        database.init_model()
    except DuffyConfigurationError as exc:
        log.error("Configuration key missing or wrong: %s", exc.args[0])
        sys.exit(1)

    shell.embed_shell(shell_type=shell_type)


# Run the backend task worker


@cli.command(context_settings={"ignore_unknown_options": True, "help_option_names": []})
@click.argument("worker_args", nargs=-1, type=click.UNPROCESSED)
def worker(worker_args: Tuple[str]):
    """Start a Celery worker to process backend tasks."""
    if not start_worker:
        raise click.ClickException("Please install the duffy[tasks] extra for this command")

    start_worker(worker_args=worker_args)


# Run the web app


@cli.command()
@click.option(
    "--reload/--no-reload", default=False, help="Automatically reload if the code is changed."
)
@click.option("-H", "--host", default=None, help="Set the host address to listen on.")
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535, clamp=True),
    default=None,
    help="Set the port value.",
)
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level.",
    default=None,
)
def serve(reload, host, port, loglevel):
    """Run the Duffy web application server.

    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance, teardown and rebuild of the Nodes
    (physical hardware and virtual machines) that are used to run
    the tests in the CI Cluster.
    """
    config_app = config.get("app", {})
    if host is None:
        host = config_app.get("host", "127.0.0.1")
    if port is None:
        port = config_app.get("port", 8080)
    if loglevel is None:
        loglevel = config_app.get("loglevel", "info")

    numeric_loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]
    logging.basicConfig(level=numeric_loglevel)

    # Report for duty
    print(" * Starting Duffy...")
    print(f" * Host address : {host}")
    print(f" * Port number  : {port}")
    print(f" * Log level    : {loglevel}")
    print(f" * Serving API docs on http://{host}:{port}/docs")

    uvicorn_log_config = copy.deepcopy(config_app.get("logging", uvicorn.config.LOGGING_CONFIG))
    if uvicorn_log_config.get("loggers", {}).get("duffy"):
        uvicorn_log_config["loggers"]["duffy"]["level"] = numeric_loglevel

    try:
        # Start the show
        uvicorn.run(
            "duffy.app.main:app",
            host=host,
            port=port,
            log_level=numeric_loglevel,
            reload=reload,
            log_config=uvicorn_log_config,
        )
    except ImportError:
        raise click.ClickException(
            "Please install the duffy[app] and optionally the duffy[postgresql] extra for this"
            " command"
        )


# Run the web app - Duffy Metaclient for Legacy Support


@cli.command()
@click.option(
    "--reload/--no-reload", default=False, help="Automatically reload if the code is changed."
)
@click.option("-H", "--host", default=None, help="Set the host address to listen on.")
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535, clamp=True),
    default=None,
    help="Set the port value.",
)
@click.option(
    "-D",
    "--dest",
    default=None,
    help="Set the destination address of Duffy deployment.",
)
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level.",
    default=None,
)
@click.pass_context
def serve_legacy(ctx, reload, host, port, dest, loglevel):
    """Serve the Duffy Metaclient for Legacy Support app.

    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance and teardown / rebuild of the Nodes
    (physical hardware for now, VMs coming soon) that are used to run
    the tests in the CI Cluster.

    This metaclient exposes older endpoints for legacy support and
    connects them to the path operations introduced by the newer version
    of the Duffy endpoint, until the support for the older endpoints is
    deprecated.
    """
    config_metaclient = config.get("metaclient", {})
    if host is None:
        host = config_metaclient.get("host", "127.0.0.1")
    if port is None:
        port = config_metaclient.get("port", 9090)
    if dest is None:
        dest = config_metaclient.get("dest", "http://127.0.0.1:8080")
    if loglevel is None:
        loglevel = config_metaclient.get("loglevel", "info")

    numeric_loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]
    logging.basicConfig(level=numeric_loglevel)

    # Report for duty
    print(" * Starting Duffy Metaclient for Legacy Support...")
    print(f" * Host address        : {host}")
    print(f" * Port number         : {port}")
    print(f" * Destination address : {dest}")
    print(f" * Log level           : {loglevel}")
    print(f" * Serving API docs on http://{host}:{port}/docs")

    uvicorn_log_config = copy.deepcopy(
        config_metaclient.get("logging", uvicorn.config.LOGGING_CONFIG)
    )
    if uvicorn_log_config.get("loggers", {}).get("duffy"):
        uvicorn_log_config["loggers"]["duffy"]["level"] = numeric_loglevel

    # Start the show
    uvicorn.run(
        "duffy.legacy.main:app",
        host=host,
        port=port,
        log_level=numeric_loglevel,
        reload=reload,
        log_config=uvicorn_log_config,
    )


# Commands for administrative tasks


class FakeAPITenant:
    is_admin = True


@cli.group()
def tenant():
    """Administrate Duffy tenants."""
    pass


@tenant.command("list")
@click.option("--quiet/--no-quiet", default=False, help="Show only tenant information.")
@click.option("--active/--all", default=True, help="Whether to list retired tenants.")
def tenant_list(quiet, active):
    """List tenants."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.list_tenants()
    if "error" in result:
        click.echo(
            f"ERROR: couldn't list tenants\nERROR DETAIL: {result['error']['detail']}", err=True
        )
        sys.exit(1)
    else:
        prefix = "OK: " if not quiet else ""
        for tenant in sorted(result["tenants"], key=lambda t: t.name):
            if active and not tenant.active:
                continue
            click.echo(f"{prefix}{tenant.name}")


@tenant.command("show")
@click.argument("name")
def tenant_show(name: str):
    """Show a tenant."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.show_tenant(name)
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        tenant = result["tenant"]
        click.echo(
            f"OK: {name}: id={tenant.id} node_quota={tenant.node_quota}"
            f" effective_node_quota={tenant.effective_node_quota}"
            f" session_lifetime={tenant.session_lifetime}"
            f" effective_session_lifetime={tenant.effective_session_lifetime}"
            f" session_lifetime_max={tenant.session_lifetime_max}"
            f" effective_session_lifetime_max={tenant.effective_session_lifetime_max}"
            f" active={tenant.active} created_at={tenant.created_at} retired_at={tenant.retired_at}"
        )


@tenant.command("create")
@click.option(
    "--is-admin/--no-is-admin",
    default=False,
    help="If the tenant should have administrative rights",
)
@click.option(
    "--node-quota",
    type=INT_OR_NONE,
    default=None,
    help="How many nodes the tenant can use at a time (optional, will use default if unset).",
)
@click.option(
    "--session-lifetime",
    type=INTERVAL_OR_NONE,
    default=None,
    help="The initial session lifetime for this tenant.",
)
@click.option(
    "--session-lifetime-max",
    type=INTERVAL_OR_NONE,
    default=None,
    help="The maximum session lifetime for this tenant.",
)
@click.argument("name")
@click.argument("ssh_key")
def tenant_create(
    name: str,
    ssh_key: str,
    is_admin: bool,
    node_quota: Optional[int],
    session_lifetime: Optional[timedelta],
    session_lifetime_max: Optional[timedelta],
):
    """Create a new tenant."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.create_tenant(
        name=name,
        ssh_key=ssh_key,
        node_quota=node_quota,
        session_lifetime=session_lifetime,
        session_lifetime_max=session_lifetime_max,
        is_admin=is_admin,
    )
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"OK: {name}: {result['tenant'].api_key}")


@tenant.command("retire")
@click.option("--retire/--unretire", default=True, help="Whether to retire or unretire a tenant.")
@click.argument("name")
def tenant_retire(name: str, retire: bool = True):
    """Retire or unretire a tenant."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.retire_unretire_tenant(name, retire=retire)
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"OK: {name}: active={result['tenant'].active}")


@tenant.command("update")
@click.option("--ssh-key", help="New SSH key for the tenant.")
@click.option(
    "--api-key", help="Either a new API key (UUID) for the tenant or 'reset' to set automatically."
)
@click.option(
    "--node-quota",
    type=INT_OR_NONE,
    default=UNSET,
    help="How many nodes the tenant can use at a time (optional, will use default if unset).",
)
@click.option(
    "--session-lifetime",
    type=INTERVAL_OR_NONE,
    default=UNSET,
    help="The initial session lifetime for this tenant.",
)
@click.option(
    "--session-lifetime-max",
    type=INTERVAL_OR_NONE,
    default=UNSET,
    help="The maximum session lifetime for this tenant.",
)
@click.argument("name")
def tenant_update(
    name: str,
    node_quota: Optional[Union[int, SentinelType]],
    session_lifetime: Optional[Union[timedelta, SentinelType]],
    session_lifetime_max: Optional[Union[timedelta, SentinelType]],
    ssh_key: str = None,
    api_key: str = None,
):
    """Update a tenant."""
    if (
        not ssh_key
        and not api_key
        and node_quota is UNSET
        and session_lifetime is UNSET
        and session_lifetime_max is UNSET
    ):
        click.echo(
            "ERROR: Either --ssh-key, --api-key, --node-quota, --session-lifetime or"
            " --session-lifetime-max must be set.",
            err=True,
        )
        sys.exit(1)
    admin_ctx = admin.AdminContext.create_for_cli()
    kwargs = {"name": name, "ssh_key": ssh_key, "api_key": api_key}
    if node_quota is not UNSET:
        kwargs["node_quota"] = node_quota
    if session_lifetime is not UNSET:
        kwargs["session_lifetime"] = session_lifetime
    if session_lifetime_max is not UNSET:
        kwargs["session_lifetime_max"] = session_lifetime_max
    result = admin_ctx.update_tenant(**kwargs)
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        tenant = result["tenant"]
        click.echo(
            f"OK: {name}: ssh_key={tenant.ssh_key} api_key={tenant.api_key}"
            f" node_quota={tenant.node_quota} effective_node_quota={tenant.effective_node_quota}"
            f" session_lifetime={tenant.session_lifetime}"
            f" effective_session_lifetime={tenant.effective_session_lifetime}"
            f" session_lifetime_max={tenant.session_lifetime_max}"
            f" effective_session_lifetime_max={tenant.effective_session_lifetime_max}"
        )


@cli.group()
@click.option("--url", help="The base URL of the Duffy API.")
@click.option("--auth-name", help="The tenant name to authenticate with the Duffy API.")
@click.option("--auth-key", help="The tenant key to authenticate with the Duffy API.")
@click.option(
    "--format",
    type=click.Choice(
        DuffyFormatter._subclasses_for_format.keys()
        if DuffyFormatter
        else ("json", "yaml", "flat"),
        case_sensitive=False,
    ),
    default="json",
    help="Format with which to print results.",
)
@click.pass_context
def client(
    ctx: click.Context,
    url: Optional[str],
    auth_name: Optional[str],
    auth_key: Optional[str],
    format: str,
):
    """Command line client for the Duffy API."""
    if not (DuffyClient and DuffyFormatter):
        raise click.ClickException("Please install the duffy[client] extra for this command")

    ctx.ensure_object(dict)
    ctx.obj["client"] = DuffyClient(url=url, auth_name=auth_name, auth_key=auth_key)
    ctx.obj["formatter"] = DuffyFormatter.new_for_format(format)


@client.command("list-sessions")
@click.pass_obj
def client_list_sessions(obj):
    """Query active sessions for this tenant on the Duffy API."""
    result = obj["client"].list_sessions()
    formatted_result = obj["formatter"].format(result)
    if formatted_result:
        click.echo(formatted_result)


@client.command("show-session")
@click.argument("session_id", type=int)
@click.pass_obj
def client_show_session(obj, session_id: int):
    """Show one session identified by its id on the Duffy API."""
    result = obj["client"].show_session(session_id)
    click.echo(obj["formatter"].format(result))


@client.command("request-session")
@click.argument(
    "nodes_specs",
    type=NODES_SPEC,
    nargs=-1,
    required=True,
    metavar="pool=<pool>:quantity=<quantity> [...]",
)
@click.pass_obj
def client_request_session(obj: dict, nodes_specs: List[str]):
    """Request a session with nodes from the Duffy API."""
    result = obj["client"].request_session(nodes_specs)
    click.echo(obj["formatter"].format(result))


@client.command("retire-session")
@click.argument("session_id", type=int)
@click.pass_obj
def client_retire_session(obj: dict, session_id: int):
    """Retire an active Duffy session."""
    result = obj["client"].retire_session(session_id)
    click.echo(obj["formatter"].format(result))
