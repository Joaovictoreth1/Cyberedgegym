import math
import time
from collections.abc import Callable

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from errors import ApiError, error_response
from settings import Settings


class ContactRateLimiter:
    def __init__(
        self, limit: int, window: int, capacity: int, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self.capacity = capacity
        self.clock = clock
        self.clients: dict[str, tuple[float, int]] = {}

    def retry_after(self, client: str) -> int | None:
        now = self.clock()
        while self.clients:
            oldest = next(iter(self.clients))
            if self.clients[oldest][0] > now:
                break
            del self.clients[oldest]
        entry = self.clients.get(client)
        if entry is None:
            if len(self.clients) == self.capacity:
                return self._remaining(self.clients[next(iter(self.clients))][0], now)
            self.clients[client] = (now + self.window, 1)
        else:
            expiry, count = entry
            if count >= self.limit:
                return self._remaining(expiry, now)
            self.clients[client] = (expiry, count + 1)
        return None

    @staticmethod
    def _remaining(expiry: float, now: float) -> int:
        return max(1, math.ceil(expiry - now))


class RequestLimitsMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.max_bytes = settings.max_request_bytes
        self.rate_limiter = ContactRateLimiter(
            settings.contact_rate_limit,
            settings.contact_rate_window_seconds,
            settings.contact_rate_max_clients,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        root_path = scope.get("root_path", "")
        path = scope["path"]
        if root_path and path.startswith(root_path + "/"):
            path = path[len(root_path) :]
        path = path.rstrip("/")
        method = scope["method"]
        contact = path == "/api/contato" and method == "POST"
        admin_write = path.startswith("/api/leads/") and method == "PATCH"
        if not contact and not admin_write:
            await self.app(scope, receive, send)
            return

        if contact:
            client = scope.get("client")
            retry = self.rate_limiter.retry_after(client[0] if client else "unknown")
            if retry is not None:
                error = ApiError(
                    429, "rate_limited", "Tente novamente mais tarde.", {"Retry-After": str(retry)}
                )
                await error_response(error)(scope, receive, send)
                return

        headers = Headers(scope=scope)
        length = headers.get("content-length")
        try:
            size = int(length) if length is not None else 0
            if size < 0:
                raise ValueError
        except ValueError:
            await error_response(ApiError(400, "invalid_content_length", "Tamanho inválido."))(
                scope, receive, send
            )
            return

        too_large = ApiError(413, "body_too_large", "Corpo da solicitação acima do limite.")
        if size > self.max_bytes:
            await error_response(too_large)(scope, receive, send)
            return

        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            await error_response(ApiError(415, "unsupported_media_type", "Use application/json."))(
                scope, receive, send
            )
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk: bytes = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                await error_response(too_large)(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        sent = False

        async def replay() -> Message:
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": bytes(body)}

        await self.app(scope, replay, send)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, production: bool) -> None:
        self.app = app
        self.production = production

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if self.production or scope["path"] not in {
                    "/docs",
                    "/docs/oauth2-redirect",
                    "/redoc",
                }:
                    headers["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'; form-action 'none'"
                    )
                if self.production:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, secured if scope["type"] == "http" else send)
