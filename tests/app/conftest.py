import pytest
from httpx import AsyncClient
from sqlalchemy import select

from duffy.app.main import app
from duffy.database import DBSession
from duffy.database.model import Tenant
from duffy.database.setup import _gen_test_api_key


def pytest_configure(config):
    config.addinivalue_line("markers", "auth_tenant")


@pytest.fixture
async def unauthenticated_client() -> AsyncClient:
    """A fixture creating an async client for testing the FastAPI app.

    This client won't attempt to authenticate API requests."""
    async with AsyncClient(app=app, base_url="http://duffy-test.example.com") as client:
        yield client


@pytest.fixture
async def auth_tenant(request: pytest.FixtureRequest, db_async_schema, db_async_model_initialized):
    """A fixture creating a tenant with a deterministic API key.

    Use pytest.mark.auth_tenant() to specify whether the tenant should
    have admin_privileges or not. In this case, it will be named
    'admin', otherwise 'tenant'. The API key will be set
    deterministically, depending on the name of the tenant:

        admin: ae6c10d0-0b13-554c-b976-a05d8a18f0cc
        tenant: a8b9899d-b128-59a1-aa86-754920b7f5ed
    """
    is_admin = False
    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "auth_tenant":
                is_admin = marker.kwargs.get("is_admin", is_admin)

    name = "admin" if is_admin else "tenant"

    async with DBSession.begin():
        tenant = (await DBSession.execute(select(Tenant).filter_by(name=name))).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                name=name, is_admin=is_admin, ssh_key="<ssh-key>", api_key=_gen_test_api_key(name)
            )
            DBSession.add(tenant)
            await DBSession.flush()
        else:
            # Tenant of the same name exists (probably because the DB is filld with test data).
            # Ensure that its API key is valid.
            tenant.api_key = _gen_test_api_key(name)

        yield tenant


@pytest.fixture
async def client(unauthenticated_client: AsyncClient, auth_tenant: Tenant):
    """A fixture creating an async client for testing the FastAPI app.

    This client will attempt to make authenticated API requests using
    the `auth_tenant` fixture."""
    client = unauthenticated_client
    client.auth = (auth_tenant.name, str(_gen_test_api_key(auth_tenant.name)))
    return client
