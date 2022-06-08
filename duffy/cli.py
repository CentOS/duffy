import copy
import logging
import sys
from datetime import timedelta
from pathlib import Path
from typing import List, Optional, Tuple, Union

import click

try:
    import uvicorn
except ImportError:  # pragma: no cover
    uvicorn = None
import xdg.BaseDirectory
import yaml

try:
    from . import admin
except ImportError:  # pragma: no cover
    admin = None
try:
    from . import database
except ImportError:  # pragma: no cover
    database = None
try:
    from . import shell
except ImportError:  # pragma: no cover
    shell = None

try:
    from .client import DuffyClient, DuffyFormatter
except ImportError:  # pragma: no cover
    DuffyClient = DuffyFormatter = None
from .configuration import config, read_configuration

try:
    from .database.migrations.main import alembic_migration
except ImportError:  # pragma: no cover
    alembic_migration = None
try:
    from .database.setup import setup_db_schema, setup_db_test_data
except ImportError:  # pragma: no cover
    setup_db_schema = setup_db_test_data = None
from .exceptions import DuffyConfigurationError
from .misc import ConfigTimeDelta

try:
    from .tasks import start_worker
except ImportError:  # pragma: no cover
    start_worker = None
from .util import UNSET, SentinelType
from .version import __version__

DEFAULT_CONFIG_LOCATIONS = ("/etc/duffy", f"{xdg.BaseDirectory.xdg_config_home}/duffy")
DEFAULT_CONFIG_PATHS = tuple(Path(loc) for loc in DEFAULT_CONFIG_LOCATIONS)

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


# CLI groups and commands


@click.group(name="duffy")
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=(
        click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False)
        if uvicorn
        else str
    ),
    help="Set the log level.",
    default=None,
)
@click.option(
    "config_paths",
    "-c",
    "--config",
    type=click.Path(exists=True),
    multiple=True,
    help=(
        "Read configuration from the specified YAML files or directories instead of the default"
        f" paths ({', '.join(DEFAULT_CONFIG_LOCATIONS)})"
    ),
    metavar="FILE_OR_DIR",
)
@click.version_option(version=__version__, prog_name="Duffy")
@click.pass_context
def cli(ctx: click.Context, loglevel: Optional[str], config_paths: Tuple[Path]):
    ctx.ensure_object(dict)
    ctx.obj["loglevel"] = loglevel

    logging.basicConfig(level=loglevel.upper() if isinstance(loglevel, str) else loglevel)

    if not config_paths:
        # Ignore non-existent default paths
        config_paths = tuple(path for path in DEFAULT_CONFIG_PATHS if path.exists())

    log.debug(f"Reading configuration from: {', '.join(str(p) for p in config_paths)}")

    read_configuration(*config_paths, clear=True, validate=True)


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
    if not (database and setup_db_schema and setup_db_test_data):
        raise click.ClickException(
            "Please install the duffy[database] extra (and optionally duffy[postgresql] or"
            " duffy[sqlite]) for this command"
        )

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
    if not alembic_migration:
        raise click.ClickException(
            "Please install the duffy[database] extra (and optionally duffy[postgresql] or"
            " duffy[sqlite]) for this command"
        )


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
    type=click.Choice(shell.get_available_shells(), case_sensitive=False) if shell else str,
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
@click.pass_obj
def serve(obj, reload, host, port):
    """Run the Duffy web application server.

    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance, teardown and rebuild of the Nodes
    (physical hardware and virtual machines) that are used to run
    the tests in the CI Cluster.
    """
    if not uvicorn:
        raise click.ClickException(
            "Please install the duffy[app] extra (and optionally duffy[postgresql] or"
            " duffy[sqlite]) for this command"
        )

    config_app = config.get("app", {})
    if host is None:
        host = config_app.get("host", "127.0.0.1")
    if port is None:
        port = config_app.get("port", 8080)
    loglevel = obj["loglevel"]
    if loglevel is None:
        loglevel = config_app.get("loglevel", "info")
    numeric_loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]

    # Report for duty
    print(" * Starting Duffy...")
    print(f" * Host address : {host}")
    print(f" * Port number  : {port}")
    print(f" * Log level    : {loglevel}")
    print(f" * Serving API docs on http://{host}:{port}/docs")

    uvicorn_log_config = copy.deepcopy(config_app.get("logging", uvicorn.config.LOGGING_CONFIG))
    if uvicorn_log_config.get("loggers", {}).get("duffy"):
        uvicorn_log_config["loggers"]["duffy"]["level"] = numeric_loglevel

    # Start the show
    uvicorn.run(
        "duffy.app.main:app",
        host=host,
        port=port,
        log_level=numeric_loglevel,
        reload=reload,
        log_config=uvicorn_log_config,
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
@click.pass_obj
def serve_legacy(obj, reload, host, port, dest):
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
    if not uvicorn:
        raise click.ClickException("Please install the duffy[legacy] extra for this command")

    config_metaclient = config.get("metaclient", {})
    if host is None:
        host = config_metaclient.get("host", "127.0.0.1")
    if port is None:
        port = config_metaclient.get("port", 9090)
    if dest is None:
        dest = config_metaclient.get("dest", "http://127.0.0.1:8080")
    loglevel = obj["loglevel"]
    if loglevel is None:
        loglevel = config_metaclient.get("loglevel", "info")
    numeric_loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]

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


@cli.group("admin")
def admin_group():
    """Administrate Duffy tenants."""
    if not admin:
        raise click.ClickException(
            "Please install the duffy[admin] extra (and optionally duffy[postgresql] or"
            " duffy[sqlite]) for this command"
        )


@admin_group.command("list-tenants")
@click.option("--quiet/--no-quiet", default=False, help="Show only tenant information.")
@click.option("--active/--all", default=True, help="Whether to list retired tenants.")
def admin_list_tenants(quiet, active):
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


@admin_group.command("show-tenant")
@click.argument("name")
def admin_show_tenant(name: str):
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


@admin_group.command("create-tenant")
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
def admin_create_tenant(
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


@admin_group.command("retire-tenant")
@click.option("--retire/--unretire", default=True, help="Whether to retire or unretire a tenant.")
@click.argument("name")
def admin_retire_tenant(name: str, retire: bool = True):
    """Retire or unretire a tenant."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.retire_unretire_tenant(name, retire=retire)
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        click.echo(f"OK: {name}: active={result['tenant'].active}")


@admin_group.command("update-tenant")
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
def admin_update_tenant(
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
    # Only print newline if formatted_result isn't empty.
    click.echo(formatted_result, nl=formatted_result)


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


@client.command("list-pools")
@click.pass_obj
def client_list_pools(obj: dict):
    """List configured Duffy node pools."""
    result = obj["client"].list_pools()
    formatted_result = obj["formatter"].format(result)
    # Only print newline if formatted_result isn't empty.
    click.echo(formatted_result, nl=formatted_result)


@client.command("show-pool")
@click.argument("name")
@click.pass_obj
def client_show_pool(obj: dict, name: str):
    """Show information about a Duffy node pool."""
    result = obj["client"].show_pool(name)
    click.echo(obj["formatter"].format(result))
