import pytest
from starlette.status import HTTP_201_CREATED

from . import BaseTestController


class TestNode(BaseTestController):
    name = "node"
    path = "/api/v1/nodes"
    attrs = {
        "hostname": "opennebula.nodes.example.com",
        "ipaddr": "192.0.2.1",
        "pool": "virtual-fedora35-x86_64-small",
    }
    unique = True

    @pytest.mark.parametrize("reusable", (True, False))
    async def test_reusable(self, reusable, client, auth_admin):
        response = await self._create_obj(client, attrs={"reusable": reusable})

        assert response.status_code == HTTP_201_CREATED
        assert response.json()["node"]["reusable"] == reusable
