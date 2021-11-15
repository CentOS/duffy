from pathlib import Path

import alembic.command
import alembic.config

from ..configuration import config

# Import the DB model here so its classes are considered by metadata.create_all() below.
from ..database import model  # noqa: F401
from . import get_sync_engine, metadata

HERE = Path(__file__).parent


def setup_db_schema():
    engine = get_sync_engine()
    with engine.begin():
        print("Creating database schema")
        metadata.create_all(bind=engine)

        print("Setting up database migrations")
        cfg = alembic.config.Config()
        cfg.set_main_option("script_location", str(HERE / "migrations"))
        cfg.set_main_option("sqlalchemy.url", config["database"]["sqlalchemy"]["sync_url"])

        alembic.command.stamp(cfg, "head")
