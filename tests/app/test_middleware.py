import uuid

from httpx import AsyncClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from duffy.app import middleware


class TestRequestIDMiddleware:
    async def test_call(self):
        def endpoint(request):
            return PlainTextResponse("Endpoint", status_code=200)

        app = Starlette(
            routes=[Route("/", endpoint=endpoint)],
            middleware=[Middleware(middleware.RequestIdMiddleware)],
        )

        async with AsyncClient(app=app, base_url="http://example.test/") as client:
            response1 = await client.get("/")
            uuid1 = uuid.UUID(response1.headers["X-Request-Id"])
            assert uuid1.version == 4

            response2 = await client.get("/")
            uuid2 = uuid.UUID(response2.headers["X-Request-Id"])
            assert uuid2.version == 4

            assert uuid1 != uuid2
