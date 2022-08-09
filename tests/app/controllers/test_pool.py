from unittest import mock

import pytest
from starlette.status import HTTP_200_OK, HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY

from duffy.database.model import Node


class MockPool(dict):
    def __init__(self, name, **kwargs):
        self.name = name
        super().__init__(**kwargs)


@pytest.mark.duffy_config(example_config=True, clear=True)
class TestPool:
    @mock.patch("duffy.app.controllers.pool.ConcreteNodePool")
    async def test_get_all_pools(self, ConcreteNodePool, client):
        ConcreteNodePool.iter_pools.return_value = [
            MockPool(name="foo"),  # missing fill-level, shouldn't be listed
            MockPool(name="bar", **{"fill-level": 64}),
        ]

        response = await client.get("/api/v1/pools")
        result = response.json()

        ConcreteNodePool.iter_pools.assert_called_once_with()

        assert result["pools"] == [{"name": "bar", "fill-level": 64}]

    @pytest.mark.parametrize("pool", ("foo", "bar", "baz"))
    @mock.patch("duffy.app.controllers.pool.ConcreteNodePool")
    async def test_get_pools(
        self, ConcreteNodePool, pool, client, db_async_session, db_async_model_initialized
    ):
        ConcreteNodePool.known_pools = {
            "foo": MockPool(name="foo"),  # missing fill-level, shouldn't be listed
            "bar": MockPool(name="bar", **{"fill-level": 64}),
        }

        async with db_async_session.begin():
            ipaddr_octet = 1
            for state, quantity in (("ready", 3), ("deployed", 2)):
                for idx in range(quantity):
                    ipaddr_octet += 1
                    db_async_session.add(
                        Node(
                            hostname=f"node-{ipaddr_octet}",
                            ipaddr=f"192.168.1.{ipaddr_octet}",
                            pool="bar",
                            state=state,
                        )
                    )

        if pool == "bar":
            expected_status = HTTP_200_OK
            expected_result = {
                "action": "get",
                "pool": {
                    "name": "bar",
                    "fill-level": 64,
                    "levels": {
                        "provisioning": 0,
                        "ready": 3,
                        "contextualizing": 0,
                        "deployed": 2,
                        "deprovisioning": 0,
                    },
                },
            }
        else:
            expected_result = None
            if pool == "foo":
                expected_status = HTTP_422_UNPROCESSABLE_ENTITY
            else:
                expected_status = HTTP_404_NOT_FOUND

        response = await client.get(f"/api/v1/pools/{pool}")
        result = response.json()

        assert response.status_code == expected_status

        if expected_result:
            assert result == expected_result
        else:
            assert "detail" in result
