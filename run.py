from flask.helpers import get_debug_flag

from duffy.app import create_app
from duffy.config import DevConfig, ProdConfig

CONFIG = DevConfig if get_debug_flag() else ProdConfig

app = create_app(CONFIG)
