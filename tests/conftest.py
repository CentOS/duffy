import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator, List, Union

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from duffy.configuration import read_configuration
from duffy.database import Base, DBSession, SyncDBSession, init_async_model, init_sync_model

# Configuration fixtures


def pytest_configure(config):
    config.addinivalue_line("markers", "duffy_config")


@pytest.fixture
def duffy_config_files(request: pytest.FixtureRequest) -> Iterator[List[Union[Path, str]]]:
    configs = []

    # Consult markers about desired configuration files and their contents.

    # request.node.iter_markers() lists markers of parent objects later, we need them early to make
    # e.g. markers on the method override those of the class.
    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "duffy_config":
                if marker.kwargs.get("clear"):
                    configs = []
                objtype = marker.kwargs.get("objtype", Path)
                assert objtype in (Path, str)
                for content in marker.args:
                    assert any(isinstance(content, t) for t in (dict, str))
                    configs.append((objtype, content))

    # Create configuration files.
    config_file_objs = []  # the NamedTemporaryFile objects
    config_file_paths = []  # their Path or str counterparts
    for objtype, content in configs:
        config_file_obj = NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".yaml", prefix="tmp_duffy_test_config", delete=False
        )
        if isinstance(content, dict):
            yaml.dump(content, stream=config_file_obj)
        else:
            print(content, file=config_file_obj)
        config_file_obj.close()
        config_file_objs.append(config_file_obj)
        config_file_paths.append(objtype(config_file_obj.name))

    # Let tests work with the configuration files.
    yield config_file_paths

    # Remove the files.
    for config_file_obj in config_file_objs:
        os.unlink(config_file_obj.name)


@pytest.fixture(autouse=True)
def duffy_config(duffy_config_files):
    read_configuration(*duffy_config_files)


# Database fixtures


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
