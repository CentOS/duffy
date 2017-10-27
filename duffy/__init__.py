import click
from flask.helpers import get_debug_flag

from duffy.app import create_app
from duffy.config import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

APP = create_app(CONFIG)

@APP.cli.command()
def initdb():
    click.echo('Working on the DB')
    pass
