"""Small ASGI bearer-token guard for the remotely deployed MCP endpoint."""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from typing import Any


ASGISend = Callable[[dict[str, Any]], Awaitable[None]]
ASGIReceive = Callable[[], Awaitable[dict[str, Any]]]


class BearerTokenAuthMiddleware:
    """Require one matching Authorization: Bearer header for every HTTP request."""

    def __init__(self, app: Callable[..., Awaitable[None]], token: bytes) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        values = [
            value
            for name, value in scope.get("headers", [])
            if name.lower() == b"authorization"
        ]
        authorized = False
        if len(values) == 1:
            scheme, separator, supplied = values[0].partition(b" ")
            authorized = (
                bool(separator)
                and scheme.lower() == b"bearer"
                and bool(supplied)
                and hmac.compare_digest(supplied, self.token)
            )

        if authorized:
            await self.app(scope, receive, send)
            return

        body = b"Unauthorized\n"
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"www-authenticate", b'Bearer realm="research-draw-mcp"'),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
