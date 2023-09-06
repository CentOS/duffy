import asyncio
from copy import deepcopy

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from ..configuration import config
from ..exceptions import DuffyConfigurationError

# use custom metadata to specify naming convention
naming_convention = {
    "ix": "%(column_0_N_label)s_index",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
metadata = MetaData(naming_convention=naming_convention)
Base = declarative_base(metadata=metadata)

async_session_maker = sessionmaker(class_=AsyncSession, expire_on_commit=False, future=True)
sync_session_maker = sessionmaker(future=True, expire_on_commit=False)


def init_sync_model(sync_engine: Engine = None):
    if not sync_engine:
        sync_engine = get_sync_engine()
    sync_session_maker.configure(bind=sync_engine)


async def init_async_model(async_engine: AsyncEngine = None):
    if not async_engine:
        async_engine = get_async_engine()
    async_session_maker.configure(bind=async_engine)


def init_model(sync_engine: Engine = None, async_engine: AsyncEngine = None):
    init_sync_model(sync_engine)
    asyncio.run(init_async_model(async_engine))


_key_failed_to_config_key = {
    "sqlalchemy": "database.sqlalchemy",
    "sync_url": "database.sqlalchemy.sync_url",
    "async_url": "database.sqlalchemy.async_url",
}


def _pgsql_disable_seqscan(
    dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
) -> None:
    """Disables the query planner's use of sequential scan plan types.

    As far as this is possible at least.

    Sequential scanning in queries can cause conflicts in concurrent transactions even if the
    respective rows accessed in the transactions are different, merely iterating over the rows “of
    the other transaction” can cause them to be locked.

    For this to work, it is necessary that the involved columns have an index, i.e. the planner has
    a usable alternative to sequential scans."""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET enable_seqscan=off")
    cursor.close()


def get_sync_engine():
    try:
        sync_config = deepcopy(config["database"]["sqlalchemy"]) or {}
        sync_config["url"] = sync_config.pop("sync_url")
    except (AttributeError, KeyError) as exc:
        key_not_found = exc.args[0]
        raise DuffyConfigurationError(
            _key_failed_to_config_key.get(key_not_found, key_not_found)
        ) from exc
    sync_config.pop("async_url", None)
    sync_config.setdefault("isolation_level", "SERIALIZABLE")
    engine = create_engine(**sync_config)
    if engine.name == "postgresql":
        event.listen(engine, "connect", _pgsql_disable_seqscan)
    return engine


def get_async_engine():
    try:
        async_config = deepcopy(config["database"]["sqlalchemy"]) or {}
        async_config["url"] = async_config.pop("async_url")
    except (AttributeError, KeyError) as exc:
        key_not_found = exc.args[0]
        raise DuffyConfigurationError(
            _key_failed_to_config_key.get(key_not_found, key_not_found)
        ) from exc
    async_config.pop("sync_url", None)
    async_config.setdefault("isolation_level", "SERIALIZABLE")
    engine = create_async_engine(**async_config)
    if engine.name == "postgresql":
        event.listen(engine.sync_engine, "connect", _pgsql_disable_seqscan)
    return engine
