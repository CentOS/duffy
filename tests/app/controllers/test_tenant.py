from uuid import uuid4

from starlette.status import HTTP_201_CREATED

from . import BaseTestController


class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "api_key": str(uuid4()),
        "ssh_key": "With a honky SSH key!",
    }
    no_response_attrs = ("api_key",)
    unique = "unique"

    async def test_with_is_admin_set(self, client):
        response = await self._create_obj(client, attrs={"is_admin": False})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])
