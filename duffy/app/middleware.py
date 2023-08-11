from contextvars import ContextVar
from typing import Optional
from uuid import uuid4

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

request_id_ctxvar: ContextVar[Optional[str]] = ContextVar("request-id", default=None)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_id = str(uuid4())
        request_id_ctxvar.set(request_id)

        if scope["type"] != "http":  # pragma: no cover
            await self.app(scope, receive, send)
            return

        async def send_with_extra_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-Id", request_id)

            await send(message)

        await self.app(scope, receive, send_with_extra_header)
