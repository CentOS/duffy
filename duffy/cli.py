import logging
import sys

import click
import uvicorn

from . import database, shell
from .configuration import config, read_configuration
from .database.setup import setup_db_schema
from .exceptions import DuffyConfigurationError
from .version import __version__

DEFAULT_CONFIG_FILE = "/etc/duffy.yaml"

log = logging.getLogger(__name__)


# Global setup and CLI options


def init_config(ctx, param, filename):
    try:
        read_configuration(filename)
    except FileNotFoundError:
        read_configuration()
    ctx.default_map = config


@click.group(name="duffy")
@click.option(
    "-c",
    "--config",
    type=click.Path(dir_okay=False),
    default=DEFAULT_CONFIG_FILE,
    callback=init_config,
    is_eager=True,
    expose_value=False,
    help="Read option defaults from the specified YAML file.",
    show_default=True,
)
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level.",
    default="info",
)
@click.version_option(version=__version__, prog_name="Duffy")
@click.pass_context
def cli(ctx, loglevel):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than serve() below)
    ctx.ensure_object(dict)

    ctx.obj["loglevel"] = loglevel
    ctx.obj["numeric_loglevel"] = numeric_loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]
    logging.basicConfig(level=numeric_loglevel)


# Set up the database tables


@cli.command()
def setup_db():
    """Create tables from the database model."""
    setup_db_schema()


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


# Run the web app


@cli.command()
@click.option(
    "--reload/--no-reload", default=False, help="Automatically reload if the code is changed."
)
@click.option("-H", "--host", default="127.0.0.1", help="Set the host address to listen on.")
@click.option(
    "-p",
    "--port",
    type=click.IntRange(1, 65535, clamp=True),
    default=8080,
    help="Set the port value.",
)
@click.pass_context
def serve(ctx, reload, host, port):
    """Run the Duffy web application server.

    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance and teardown / rebuild of the Nodes
    (physical hardware for now, VMs coming soon) that are used to run
    the tests in the CI Cluster.
    """
    loglevel = ctx.obj["loglevel"]
    numeric_loglevel = ctx.obj["numeric_loglevel"]

    # Report for duty
    print(" * Starting Duffy...")
    print(f" * Host address : {host}")
    print(f" * Port number  : {port}")
    print(f" * Log level    : {loglevel}")
    print(f" * Serving API docs on http://{host}:{port}/docs")

    uvicorn_log_config = config.get("logging", uvicorn.config.LOGGING_CONFIG).copy()
    if uvicorn_log_config.get("loggers", {}).get("duffy"):
        uvicorn_log_config["loggers"]["duffy"]["level"] = numeric_loglevel

    try:
        database.init_model()
    except DuffyConfigurationError as exc:
        log.error("Configuration key missing or wrong: %s", exc.args[0])
        sys.exit(1)

    # Start the show
    uvicorn.run(
        "duffy.app.main:app",
        host=host,
        port=port,
        log_level=numeric_loglevel,
        reload=reload,
        log_config=uvicorn_log_config,
    )
