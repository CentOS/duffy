import uuid

import pytest
from starlette.status import HTTP_201_CREATED, HTTP_403_FORBIDDEN

from duffy.database.setup import _gen_test_api_key

from . import BaseTestController


class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "api_key": str(uuid.uuid4()),
        "ssh_key": "With a honky SSH key!",
    }
    no_verify_attrs = ("api_key", "ssh_key")
    unique = "unique"

    async def test_with_is_admin_set(self, client):
        response = await self._create_obj(client, attrs={"is_admin": False})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])

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
