import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from duffy.database import Base, DBSession, init_model


@pytest.fixture
def db_engine():
    db_engine = create_engine("sqlite:///:memory:", future=True, echo=True)
    return db_engine


@pytest.fixture
def db_async_engine():
    async_db_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=True)
    return async_db_engine


@pytest.fixture
def db_schemas(db_engine):
    with db_engine.begin():
        Base.metadata.create_all(db_engine)


@pytest.fixture
def db_model_initialized(db_engine, db_schemas):
    init_model(engine=db_engine)


@pytest.fixture
def db_obj(request, db_model_initialized):
    with DBSession.begin():
        db_obj_dependencies = request.instance._db_obj_get_dependencies()
        attrs = {**request.instance.attrs, **db_obj_dependencies}
        obj = request.instance.klass(**attrs)
        obj._db_obj_dependencies = db_obj_dependencies
        DBSession.add(obj)
        DBSession.flush()

        yield obj

        DBSession.rollback()
