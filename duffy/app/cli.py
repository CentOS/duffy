import click
import uvicorn

from ..version import __version__


@click.command()
@click.option("-p", "--portnumb", "portnumb", help="Set the port value [0-65536]", default=8080)
@click.option(
    "-6",
    "--ipv6",
    "netprotc",
    flag_value="ipv6",
    help="Start the server on an IPv6 address",
)
@click.option(
    "-4",
    "--ipv4",
    "netprotc",
    flag_value="ipv4",
    help="Start the server on an IPv4 address",
)
@click.option(
    "-l",
    "--loglevel",
    "loglevel",
    type=click.Choice(list(uvicorn.config.LOG_LEVELS.keys()), case_sensitive=False),
    help="Set the log level",
    default="info",
)
@click.version_option(version=__version__, prog_name="Duffy")
def main(portnumb, netprotc, loglevel):
    """
    Duffy is the middle layer running ci.centos.org that manages the
    provisioning, maintenance and teardown / rebuild of the Nodes
    (physical hardware for now, VMs coming soon) that are used to run
    the tests in the CI Cluster.
    """
    print(" * Starting Duffy...")
    print(" * Port number : %s" % portnumb)
    if netprotc == "ipv6":
        print(" * IP version  : 6")
        netpdata = "::"
    else:
        print(" * IP version  : 4")
        netpdata = "0.0.0.0"
    print(" * Log level   : %s" % loglevel)
    uvicorn.run("duffy.app.main:app", host=netpdata, port=portnumb, log_level=loglevel)
