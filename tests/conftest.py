from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator, List, Union

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from duffy.configuration import read_configuration
from duffy.database import (
    Base,
    async_session_maker,
    init_async_model,
    init_sync_model,
    sync_session_maker,
)
from duffy.database.setup import _gen_test_data_objs

HERE = Path(__file__).parent
EXAMPLE_CONFIG = HERE.parent / "etc" / "duffy-example-config.yaml"

# Configuration fixtures


def pytest_configure(config):
    config.addinivalue_line("markers", "duffy_config")


@pytest.fixture
def duffy_config_files(
    request: pytest.FixtureRequest, tmp_path: Path
) -> Iterator[List[Union[Path, str]]]:
    """Fixture to create testing configuration files.

    This is useful mainly to the duffy_config fixture which is applied
    universally, unless you need access to the actual configuration
    files.

    Use `@pytest.mark.duffy_config()` to affect their content(s), e.g.:

        TEST_CONFIG = {...}

        @pytest.mark.duffy_config(TEST_CONFIG)
        def test_something(duffy_config_files):
            # duffy_config_files is a list containing 1 Path object
            # pointing to the temporary configuration file initialized
            # from TEST_CONFIG
            ...
    """
    configs = []

    EXAMPLE_CONFIG_SENTINEL = object()

    # Consult markers about desired configuration files and their contents.

    # request.node.iter_markers() lists markers of parent objects later, we need them early to make
    # e.g. markers on the method override those on the class.
    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "duffy_config":
                if marker.kwargs.get("clear"):
                    configs = []
                objtype = marker.kwargs.get("objtype", Path)
                assert objtype in (Path, str)
                if marker.kwargs.get("example_config"):
                    configs.append((objtype, EXAMPLE_CONFIG_SENTINEL))
                for content in marker.args:
                    assert any(isinstance(content, t) for t in (dict, str))
                    configs.append((objtype, content))

    # Create configuration files.
    config_file_paths = []  # their Path or str counterparts
    for objtype, content in configs:
        if content is EXAMPLE_CONFIG_SENTINEL:
            config_file_paths.append(EXAMPLE_CONFIG.absolute())
            continue

        config_file_obj = NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".yaml", prefix="tmp_duffy_test_config", delete=False
        )
        if isinstance(content, dict):
            yaml.dump(content, stream=config_file_obj)
        else:
            print(content, file=config_file_obj)
        config_file_obj.close()
        config_file_paths.append(objtype(config_file_obj.name))

    # Let tests work with the configuration files.
    yield config_file_paths


@pytest.fixture(autouse=True)
def duffy_config(duffy_config_files):
    """Fixture to apply temporary configuration files in tests.

    This loads the configuration files which are specified using
    @pytest.mark.duffy_config(...) (see duffy_config_files) and applies
    them in duffy.configuration.config.
    """
    read_configuration(*duffy_config_files, clear=True)


# Database fixtures


@pytest.fixture
def db_sync_engine():
    """A fixture which creates a synchronous database engine."""
    db_engine = create_engine("sqlite:///:memory:", future=True, echo=True)
    return db_engine


@pytest.fixture
def db_async_engine():
    """A fixture which creates an asynchronous database engine."""
    async_db_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=True)
    return async_db_engine


@pytest.fixture
def db_sync_schema(db_sync_engine):
    """Synchronous fixture to install the database schema."""
    with db_sync_engine.begin():
        Base.metadata.create_all(db_sync_engine)


@pytest.fixture
async def db_async_schema(db_async_engine):
    """Asynchronous fixture to install the database schema."""
    async with db_async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def db_sync_model_initialized(db_sync_engine, db_sync_schema):
    """Fixture to initialize the synchronous DB model.

    This is used so db_sync_session is usable in tests.
    """
    init_sync_model(sync_engine=db_sync_engine)


@pytest.fixture
async def db_async_model_initialized(db_async_engine, db_async_schema):
    """Fixture to initialize the asynchronous DB model.

    This is used so db_async_session is usable in tests.
    """
    await init_async_model(async_engine=db_async_engine)


@pytest.fixture
def db_sync_session(db_sync_model_initialized):
    """Fixture setting up a synchronous DB session."""
    db_session = sync_session_maker()
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture
async def db_async_session(db_async_model_initialized):
    """Fixture setting up an asynchronous DB session."""
    db_session = async_session_maker()
    try:
        yield db_session
    finally:
        await db_session.close()


@pytest.fixture
def db_sync_obj(request, db_sync_session):
    """Fixture to create an object of a tested model type.

    This is for synchronous test functions/methods."""
    with db_sync_session.begin():
        db_obj_dependencies = request.instance._db_obj_get_dependencies()
        attrs = {**request.instance.attrs, **db_obj_dependencies}
        obj = request.instance.klass(**attrs)
        obj._db_obj_dependencies = db_obj_dependencies
        db_sync_session.add(obj)
        db_sync_session.flush()

        yield obj

        db_sync_session.rollback()


@pytest.fixture
async def db_async_obj(request, db_async_session):
    """Fixture to create an object of a tested model type.

    This is for asynchronous test functions/methods."""
    async with db_async_session.begin():
        db_obj_dependencies = request.instance._db_obj_get_dependencies()
        attrs = {**request.instance.attrs, **db_obj_dependencies}
        obj = request.instance.klass(**attrs)
        obj._db_obj_dependencies = db_obj_dependencies
        db_async_session.add(obj)
        await db_async_session.flush()

        yield obj

        await db_async_session.rollback()


@pytest.fixture
def db_sync_test_data(db_sync_session):
    """A fixture to fill the DB with test data.

    Use this in synchronous tests.
    """
    with db_sync_session.begin():
        for obj in _gen_test_data_objs():
            db_sync_session.add(obj)


@pytest.fixture
async def db_async_test_data(db_async_session):
    """A fixture to fill the DB with test data.

    Use this in asynchronous tests.
    """
    async with db_async_session.begin():
        for obj in _gen_test_data_objs():
            db_async_session.add(obj)


@pytest.fixture(scope="session")
def test_mechanism():
    """A fixture which provides a no-op "test" mechanism."""
    # This is scoped for the session to ensure that only one mechanism class for type "test" exists.
    from duffy.nodes.mechanisms import Mechanism

    class TestMechanism(Mechanism, mech_type="test"):
        pass

    return TestMechanism
