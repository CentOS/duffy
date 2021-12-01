from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from . import BaseTestController
from .test_chassis import TestChassis as _TestChassis


class TestOpenNebulaNode(BaseTestController):

    name = "node"
    path = "/api/v1/nodes"
    attrs = {
        "type": "opennebula",
        "hostname": "opennebula.nodes.example.com",
        "ipaddr": "192.0.2.1",
        "flavour": "medium",
    }
    unique = True


class TestSeaMicroNode(BaseTestController):

    name = "node"
    path = "/api/v1/nodes"
    attrs = {
        "type": "seamicro",
        "hostname": "seamicro.nodes.example.com",
        "ipaddr": "192.0.2.2",
        "chassis_id": (_TestChassis, "id"),
    }
    unique = True

    async def test_create_unknown_chassis(self, client):
        response = await self._create_obj(client, add_attrs={"chassis_id": 1})
        assert response.status_code == HTTP_422_UNPROCESSABLE_ENTITY
        result = response.json()
        assert "detail" in result
