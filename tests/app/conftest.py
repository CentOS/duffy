import pytest
from httpx import AsyncClient

from duffy.app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(app=app, base_url="http://duffy-test.example.com") as client:
        yield client
