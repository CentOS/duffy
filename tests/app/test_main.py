from html.parser import HTMLParser
from unittest import mock

import pytest

from duffy.app.main import app, init_model, init_tasks
from duffy.exceptions import DuffyConfigurationError

from ..util import noop_context


@pytest.mark.client_auth_as(None)
class TestMain:
    api_paths = (
        "/api/v1/nodes",
        "/api/v1/tenants",
        "/api/v1/sessions",
    )

    @pytest.mark.parametrize("path", api_paths)
    def test_paths(self, path):
        assert any(r.path == path for r in app.routes)

    async def test_openapi_json(self, client):
        response = await client.get("/openapi.json")
        result = response.json()
        assert isinstance(result["openapi"], str)
        assert all(x in result["paths"] for x in self.api_paths)

    async def test_swagger_docs(self, client):
        """Test that Swagger UI docs render and can be parsed."""
        response = await client.get("/docs")
        parser = HTMLParser()
        parser.feed(response.text)

    async def test_redoc_docs(self, client):
        """Test that ReDoc docs render and can be parsed."""
        response = await client.get("/redoc")
        parser = HTMLParser()
        parser.feed(response.text)

    @pytest.mark.parametrize("config_error", (False, True))
    @mock.patch("duffy.database.init_async_model")
    @mock.patch("duffy.database.init_sync_model")
    async def test_init_model(self, init_sync_model, init_async_model, config_error):
        if config_error:
            init_sync_model.side_effect = DuffyConfigurationError("database")
            expectation = pytest.raises(SystemExit)
        else:
            expectation = noop_context()

        with expectation as excinfo:
            await init_model()

        init_sync_model.assert_called_once_with()
        if config_error:
            init_async_model.assert_not_awaited()
            assert excinfo.value.code != 0
        else:
            init_async_model.assert_awaited_once_with()

    @mock.patch("duffy.app.main.tasks")
    def test_init_tasks(self, tasks):
        init_tasks()
        tasks.init_tasks.assert_called_once_with()
