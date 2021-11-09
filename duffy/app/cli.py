import click
import uvicorn

from ..configuration import config, read_configuration
from ..version import __version__

DEFAULT_CONFIG_FILE = "/etc/duffy.yaml"


def init_config(ctx, param, filename):
    try:
        read_configuration(filename)
    except FileNotFoundError:
        read_configuration()
    ctx.default_map = config


@click.command(name="duffy")
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
    "--reload/--no-reload", default=False, help="Automatically reload if the code is changed."
)
@click.option("-H", "--host", help="Set the host address to listen on.")
@click.option("-p", "--port", type=click.IntRange(1, 65535, clamp=True), help="Set the port value.")
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level.",
    default="info",
)
@click.version_option(version=__version__, prog_name="Duffy")
def main(host, port, loglevel):
    """
    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance and teardown / rebuild of the Nodes
    (physical hardware for now, VMs coming soon) that are used to run
    the tests in the CI Cluster.
    """
    # Report for duty
    print(" * Starting Duffy...")
    print(f" * Host address : {host}")
    print(f" * Port number  : {port}")
    print(f" * Log level    : {loglevel}")

    # Convert loglevel string back to int value
    loglevel = uvicorn.config.LOG_LEVELS[loglevel.lower()]

    # Start the show
    uvicorn.run("duffy.app.main:app", host=host, port=port, log_level=loglevel, reload=reload)
