from contextlib import nullcontext
from html.parser import HTMLParser
from unittest import mock

import pytest

from duffy.app.main import app, lifespan
from duffy.exceptions import DuffyConfigurationError


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

    @pytest.mark.parametrize(
        "config_error", (False, True), ids=("without-config-error", "with-config-error")
    )
    async def test_lifespan(self, config_error: bool):
        with mock.patch("duffy.app.main.NodePool") as NodePool, mock.patch(
            "duffy.database.init_async_model"
        ) as init_async_model, mock.patch(
            "duffy.database.init_sync_model"
        ) as init_sync_model, mock.patch("duffy.app.main.tasks") as tasks:
            if config_error:
                init_sync_model.side_effect = DuffyConfigurationError("database")
                expectation = pytest.raises(SystemExit)
            else:
                expectation = nullcontext()

            with expectation as exc_info:
                app = object()
                async with lifespan(app):
                    pass

        NodePool.process_configuration.assert_called_once_with()
        init_sync_model.assert_called_once_with()

        if config_error:
            init_async_model.assert_not_awaited()
            assert exc_info.value.code != 0

            tasks.init_tasks.assert_not_called()
        else:
            init_async_model.assert_awaited_once_with()
            tasks.init_tasks.assert_called_once_with()
