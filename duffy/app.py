# -*- coding: utf-8 -*-
"""The main application module for duffy."""
from flask import Flask

from duffy import api_v1
from duffy.types import seamicro

from duffy.extensions import db, migrate, marshmallow
from duffy.config import ProdConfig,DevConfig


def create_app(config_object=DevConfig):
    app = Flask(__name__.split('.')[0])
    app.config.from_object(config_object)
    app.config.from_pyfile('/etc/duffy.conf')
    register_extensions(app)
    register_blueprints(app)
    register_errorhandlers(app)
    return app


def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    marshmallow.init_app(app)
    return None


def register_blueprints(app):
    app.register_blueprint(api_v1.views.blueprint)
    app.register_blueprint(seamicro.views.blueprint)
    return None


def register_errorhandlers(app):
    return None
