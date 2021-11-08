import click
import uvicorn

from ..version import __version__


@click.command()
@click.option("-H", "--host", "host", help="Set the host address to listen on")
@click.option("-p", "--port", "port", type=int, help="Set the port value [0-65536]")
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level",
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

    # Start the show
    uvicorn.run("duffy.app.main:app", host=host, port=port, log_level=loglevel)
