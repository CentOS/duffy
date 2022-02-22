import logging
from pathlib import Path

import alembic.command
import alembic.config

from ...configuration import config

log = logging.getLogger(__name__)

HERE = Path(__file__).parent


class AlembicMigration:
    """Glue Duffy (mainly its config) and Alembic DB migrations together."""

    @property
    def config(self):
        if not hasattr(self, "_config"):
            self._config = alembic.config.Config()
            self._config.set_main_option("script_location", str(HERE.absolute()))
            self._config.set_main_option(
                "sqlalchemy.url", config["database"]["sqlalchemy"]["sync_url"]
            )
        return self._config

    def create(self, comment: str, autogenerate: bool):
        alembic.command.revision(config=self.config, message=comment, autogenerate=autogenerate)

        if autogenerate:
            log.warning(
                ">>> Remember to edit the autogenerated migration script! Unedited, it would drop"
                " any support table not registered with your SQLAlchemy metadata."
            )

    def db_version(self):
        alembic.command.current(self.config)

    def upgrade(self, version: str):
        alembic.command.upgrade(self.config, version)

    def downgrade(self, version: str):
        alembic.command.downgrade(self.config, version)


alembic_migration = AlembicMigration()
