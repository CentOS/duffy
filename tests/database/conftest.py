import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from duffy.database import Base, DBSession, SyncDBSession, init_async_model, init_sync_model


@pytest.fixture
def db_sync_engine():
    db_engine = create_engine("sqlite:///:memory:", future=True, echo=True)
    return db_engine


@pytest.fixture
def db_async_engine():
    async_db_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=True)
    return async_db_engine


@pytest.fixture
def db_sync_schema(db_sync_engine):
    with db_sync_engine.begin():
        Base.metadata.create_all(db_sync_engine)


@pytest.fixture
async def db_async_schema(db_async_engine):
    async with db_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def db_sync_model_initialized(db_sync_engine, db_sync_schema):
    init_sync_model(sync_engine=db_sync_engine)


@pytest.fixture
async def db_async_model_initialized(db_async_engine, db_async_schema):
    await init_async_model(async_engine=db_async_engine)


@pytest.fixture
def db_sync_obj(request, db_sync_model_initialized):
    with SyncDBSession.begin():
        db_obj_dependencies = request.instance._db_obj_get_dependencies()
        attrs = {**request.instance.attrs, **db_obj_dependencies}
        obj = request.instance.klass(**attrs)
        obj._db_obj_dependencies = db_obj_dependencies
        SyncDBSession.add(obj)
        SyncDBSession.flush()

        yield obj

        SyncDBSession.rollback()


@pytest.fixture
async def db_async_obj(request, db_async_model_initialized):
    async with DBSession.begin():
        db_obj_dependencies = request.instance._db_obj_get_dependencies()
        attrs = {**request.instance.attrs, **db_obj_dependencies}
        obj = request.instance.klass(**attrs)
        obj._db_obj_dependencies = db_obj_dependencies
        DBSession.add(obj)
        await DBSession.flush()

        yield obj

        await DBSession.rollback()
