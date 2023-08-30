import logging
import uuid
from contextlib import nullcontext
from unittest import mock

import pytest
from httpx import AsyncClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from duffy.app import middleware
from duffy.app.logging import RequestIdFilter
from duffy.cli import LOGGING_FORMAT


@pytest.fixture(params=["real-uuid", "fake-uuid"])
def uuid_kind(request):
    if request.param == "real-uuid":
        uuid_handling_context = mock.patch.object(middleware, "uuid4")
    else:
        uuid_handling_context = nullcontext()

    with uuid_handling_context:
        if request.param == "real-uuid":
            middleware.uuid4 = uuid.uuid4
        yield request.param


class TestRequestIDMiddleware:
    async def run_basic_test(self, uuid_kind, client, caplog):
        if uuid_kind == "real-uuid":
            expected_uuid_version = 4
        else:
            expected_uuid_version = None

        response1 = await client.get("/")
        req_uuid1 = uuid.UUID(response1.headers["X-Request-Id"])
        assert req_uuid1.version == expected_uuid_version

        response2 = await client.get("/")
        req_uuid2 = uuid.UUID(response2.headers["X-Request-Id"])
        assert req_uuid2.version == expected_uuid_version

        assert req_uuid1 != req_uuid2

        # The following kind of assumes that something is logged while processing the request. 🤞
        caplog.handler.addFilter(RequestIdFilter())
        caplog.handler.setFormatter(logging.Formatter(fmt=LOGGING_FORMAT))
        with caplog.at_level(level=logging.DEBUG):
            response = await client.get("/")

        req_id = response.headers["X-Request-Id"]
        assert all(getattr(r, "request_id", None) == req_id for r in caplog.records)
        assert all(req_id in line for line in caplog.text.split("\n") if line.strip())

    async def test_in_minimal_app(self, uuid_kind, caplog):
        log = logging.getLogger("test")
        log.addFilter(RequestIdFilter())

        def endpoint(request):
            return PlainTextResponse("Endpoint", status_code=200)

        app = Starlette(
            routes=[Route("/", endpoint=endpoint)],
            middleware=[Middleware(middleware.RequestIdMiddleware)],
        )

        async with AsyncClient(app=app, base_url="http://example.test/") as client:
            await self.run_basic_test(uuid_kind, client, caplog)

    async def test_in_duffy_app(self, uuid_kind, client, caplog):
        await self.run_basic_test(uuid_kind, client, caplog)
