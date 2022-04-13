import copy
import logging
import sys
from typing import Tuple

import click
import uvicorn
import yaml

from . import admin, database, shell
from .configuration import config, read_configuration
from .database.migrations.main import alembic_migration
from .database.setup import setup_db_schema, setup_db_test_data
from .exceptions import DuffyConfigurationError
from .tasks import start_worker
from .version import __version__

DEFAULT_CONFIG_FILE = "/etc/duffy"

log = logging.getLogger(__name__)


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
    """Create a new migration."""
    alembic_migration.create(comment=" ".join(comment), autogenerate=autogenerate)


@migration.command("db-version")
def migration_db_version():
    alembic_migration.db_version()


@migration.command("upgrade")
@click.argument("version", default="head")
def migration_upgrade(version):
    alembic_migration.upgrade(version)


@migration.command("downgrade")
@click.argument("version", default="-1")
def migration_downgrade(version):
    alembic_migration.downgrade(version)


# Interactive shell


@cli.command(name="shell")
@click.option(
    "-t",
    "--shell-type",
    type=click.Choice(shell.get_available_shells(), case_sensitive=False),
    help="Type of interactive shell to use.",
    default=None,
)
def run_shell(shell_type: str):
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
            f"OK: {name}: id={tenant.id} active={tenant.active} created_at={tenant.created_at}"
            + f" retired_at={tenant.retired_at}"
        )


@tenant.command("create")
@click.option(
    "--is-admin/--no-is-admin",
    default=False,
    help="If the tenant should have administrative rights",
)
@click.argument("name")
@click.argument("ssh_key")
def tenant_create(name: str, ssh_key: str, is_admin: bool = False):
    """Create a new tenant."""
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.create_tenant(name, ssh_key, is_admin)
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
@click.argument("name")
def tenant_update(name: str, ssh_key: str = None, api_key: str = None):
    """Update a tenant."""
    if not ssh_key and not api_key:
        click.echo("ERROR: Either --ssh-key or --api-key must be set.", err=True)
        sys.exit(1)
    admin_ctx = admin.AdminContext.create_for_cli()
    result = admin_ctx.update_tenant(name, ssh_key=ssh_key, api_key=api_key)
    if "error" in result:
        click.echo(f"ERROR: {name}\nERROR DETAIL: {result['error']['detail']}", err=True)
        sys.exit(1)
    else:
        click.echo(
            f"OK: {name}: ssh_key={result['tenant'].ssh_key}"
            + f" api_key={result['tenant'].api_key}"
        )
