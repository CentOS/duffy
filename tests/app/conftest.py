from itertools import count
from typing import Iterator
from unittest import mock
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from duffy.app.main import app
from duffy.database.model import Tenant
from duffy.database.setup import _gen_test_api_key


def pytest_configure(config):
    config.addinivalue_line("markers", "client_auth_as")
    config.addinivalue_line("markers", "auth_tenant")


@pytest.fixture
async def auth_admin(db_async_session) -> Iterator[Tenant]:
    """A fixture creating an admin tenant with a deterministic API key.

    The API key will be set deterministically, depending on the name of
    the tenant ('admin'): ae6c10d0-0b13-554c-b976-a05d8a18f0cc
    """
    async with db_async_session.begin():
        admin = (
            await db_async_session.execute(select(Tenant).filter_by(name="admin"))
        ).scalar_one_or_none()
        if not admin:
            admin = Tenant(
                name="admin",
                is_admin=True,
                ssh_key="<ssh-key>",
                api_key=_gen_test_api_key("admin"),
            )
            db_async_session.add(admin)
            await db_async_session.flush()
        else:
            # Tenant of the same name exists (probably because the DB is filld with test data).
            # Ensure that its API key and active attribute are valid.
            admin.api_key = _gen_test_api_key("admin")

    yield admin


@pytest.fixture
async def auth_tenant(request: pytest.FixtureRequest, db_async_session) -> Iterator[Tenant]:
    """A fixture creating a tenant with a deterministic API key.

    Use pytest.mark.auth_tenant(active=...) to specify whether the tenant should
    be active or not.

    The API key will be set deterministically, depending on the name of
    the tenant ('tenant'): a8b9899d-b128-59a1-aa86-754920b7f5ed
    """
    active = True
    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "auth_tenant":
                active = marker.kwargs.get("active", active)

    async with db_async_session.begin():
        tenant = (
            await db_async_session.execute(select(Tenant).filter_by(name="tenant"))
        ).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                name="tenant",
                is_admin=False,
                active=active,
                ssh_key="<ssh-key>",
                api_key=_gen_test_api_key("tenant"),
            )
            db_async_session.add(tenant)
            await db_async_session.flush()
        else:
            # Tenant of the same name exists (probably because the DB is filld with test data).
            # Ensure that its API key and active attribute are valid.
            tenant.api_key = _gen_test_api_key("tenant")
            tenant.active = active

    yield tenant


@pytest.fixture
async def client(
    request: pytest.FixtureRequest, auth_admin: Tenant, auth_tenant: Tenant
) -> Iterator[AsyncClient]:
    """A fixture creating an async client for testing the FastAPI app.

    This client will attempt to make authenticated API requests using
    the `auth_tenant` fixture."""
    auth = (auth_tenant.name, str(_gen_test_api_key(auth_tenant.name)))

    for node in request.node.listchain():
        for marker in node.own_markers:
            if marker.name == "client_auth_as":
                if not marker.args or marker.args[0] is None:
                    auth = None
                elif len(marker.args) > 1:
                    raise ValueError("client takes no more than one argument")
                else:
                    name = marker.args[0]
                    for auth_obj in (auth_admin, auth_tenant):
                        if name == auth_obj.name:
                            auth = (auth_obj.name, str(_gen_test_api_key(auth_obj.name)))
                            break
                    else:
                        raise ValueError(f"can't create client for tenant with name '{name}'")

    async with AsyncClient(app=app, base_url="http://duffy-test.example.com", auth=auth) as client:
        yield client


def _gen_fake_uuid():
    for value in count():
        yield UUID(f"{value:032}")


@pytest.fixture(autouse=True)
def fake_request_ids(request):
    with mock.patch("duffy.app.middleware.uuid4") as uuid4:
        uuid4.side_effect = _gen_fake_uuid()
        yield
