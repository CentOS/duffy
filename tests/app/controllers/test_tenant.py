import uuid

import pytest
from sqlalchemy import select
from starlette.status import HTTP_201_CREATED, HTTP_403_FORBIDDEN

from duffy.database.model import Tenant
from duffy.database.setup import _gen_test_api_key

from . import BaseTestController


class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "ssh_key": "With a honky SSH key!",
    }
    no_verify_attrs = ("ssh_key",)
    unique = "unique"

    async def test_create_obj_with_is_admin_set(self, client):
        response = await self._create_obj(client, attrs={"is_admin": False})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])

    async def test_create_obj_verify_api_key(self, client, db_async_session):
        response = await self._create_obj(client)
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        api_tenant = result[self.name]
        api_key = uuid.UUID(api_tenant["api_key"])
        created_tenant = (
            await db_async_session.execute(select(Tenant).filter_by(id=api_tenant["id"]))
        ).scalar_one()
        assert created_tenant.validate_api_key(api_key)

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_obj_other_tenant(self, client, auth_admin):
        other_tenant_response = await self._create_obj(
            client,
            attrs={"name": "Another Tenant"},
            client_kwargs={"auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))},
        )
        other_tenant_id = other_tenant_response.json()["tenant"]["id"]
        response = await client.get(f"{self.path}/{other_tenant_id}")
        assert response.status_code == HTTP_403_FORBIDDEN

    @pytest.mark.client_auth_as("tenant")
    async def test_retrieve_collection_filtered(self, client, auth_admin, auth_tenant):
        await self._create_obj(
            client,
            attrs={"name": "Another Tenant"},
            client_kwargs={"auth": (auth_admin.name, str(_gen_test_api_key(auth_admin.name)))},
        )
        response = await client.get(self.path)
        result = response.json()
        assert all(tenant["id"] == auth_tenant.id for tenant in result["tenants"])
