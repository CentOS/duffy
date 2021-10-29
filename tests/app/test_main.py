import pytest


class TestMain:

    endpoint_to_methodname = {
        # legacy API
        "/Node/get": "get_a_node",
        "/Node/done": "node_is_done",
        "/Node/fail": "node_failed",
        "/Inventory": "get_node_inventory",
        # versioned API
        "/api/v1/node/get": "get_a_node",
        "/api/v1/node/done": "node_is_done",
        "/api/v1/node/fail": "node_failed",
        "/api/v1/node": "get_node_inventory",
    }

    @pytest.mark.parametrize("endpoint", endpoint_to_methodname)
    def test_endpoints(self, endpoint, client):
        methodname = self.endpoint_to_methodname[endpoint]
        response = client.get(endpoint)
        assert response.status_code == 200
        assert response.json() == {"name": methodname}
