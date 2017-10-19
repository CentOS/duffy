# -*- coding: utf-8 -*-
"""Register any flask extensions that we use."""
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
migrate = Migrate()
marshmallow = Marshmallow()
