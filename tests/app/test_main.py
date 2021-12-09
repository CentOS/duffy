from html.parser import HTMLParser

import pytest

from duffy.app.main import app


@pytest.mark.asyncio
class TestMain:
    api_paths = (
        "/api/v1/chassis",
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
