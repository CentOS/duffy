from starlette.status import HTTP_201_CREATED

from . import BaseTestController


class TestTenant(BaseTestController):

    name = "tenant"
    path = "/api/v1/tenants"
    attrs = {
        "name": "Some Honky Tenant!",
        "ssh_key": "With a honky SSH key!",
    }
    unique = "unique"

    async def test_with_is_admin_set(self, client):
        response = await self._create_obj(client, attrs={"is_admin": False})
        assert response.status_code == HTTP_201_CREATED
        result = response.json()
        self._verify_item(result[self.name])
