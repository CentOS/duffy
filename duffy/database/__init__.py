import asyncio
from copy import deepcopy

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from ..configuration import config


# use custom metadata to specify naming convention
def constraint_column_names(constraint, table):
    return "_".join(c.name for c in constraint.columns)


def constraint_column_labels(constraint, table):  # pragma: no cover
    return "_".join(c._label for c in constraint.columns)


naming_convention = {
    "column_names": constraint_column_names,
    "column_labels": constraint_column_labels,
    "ix": "%(column_labels)s_index",
    "uq": "%(table_name)s_%(column_names)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_names)s_%(referred_table_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=naming_convention)

Base = declarative_base(metadata=metadata)

# Global session manager: DBSession() returns the thread-local session object appropriate for the
# current web request.
async_maker = sessionmaker(class_=AsyncSession, future=True)
DBSession = async_scoped_session(async_maker, scopefunc=asyncio.current_task)

sync_maker = sessionmaker(future=True)
SyncDBSession = scoped_session(sync_maker)


def init_sync_model(sync_engine: Engine = None):
    if not sync_engine:
        sync_engine = get_sync_engine()
    SyncDBSession.remove()
    SyncDBSession.configure(bind=sync_engine)


async def init_async_model(async_engine: AsyncEngine = None):
    if not async_engine:
        async_engine = get_async_engine()
    await DBSession.remove()
    DBSession.configure(bind=async_engine)


def init_model(sync_engine: Engine = None, async_engine: AsyncEngine = None):
    init_sync_model(sync_engine)
    asyncio.run(init_async_model(async_engine))


def get_sync_engine():
    sync_config = deepcopy(config["database"]["sqlalchemy"])
    sync_config["url"] = sync_config.pop("sync_url")
    sync_config.pop("async_url", None)
    return create_engine(**sync_config)


def get_async_engine():
    async_config = deepcopy(config["database"]["sqlalchemy"])
    async_config["url"] = async_config.pop("async_url")
    async_config.pop("sync_url", None)
    return create_async_engine(**async_config)
