import click
from flask.helpers import get_debug_flag

from duffy.app import create_app
from duffy.config import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

APP = create_app(CONFIG)

@APP.cli.command()
def initdb():
    from duffy.data import _populate_test_data
    # TODO: Warn if ran without an up-to-date-db
    click.echo('Initializing the DB...')
    _populate_test_data()
