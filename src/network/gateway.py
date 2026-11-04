"""The single door of the server: what kind of client is knocking?

A terminal client starts with a JSON line. A browser starts with an HTTP
request: either page of the web client or the upgrade to a WebSocket. All
three share one port, so one tunnel (or one open port) is enough.
"""

import asyncio
import contextlib
from pathlib import Path

from src.network.protocol import JsonStream, MessageStream
from src.network.websocket import WebSocketStream, accept_key

WEBSOCKET_PATH = "/ws"
_MAX_HEADERS = 64

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Gateway:
    """Tells the clients apart and hands the game a `MessageStream` for each."""

    def __init__(self, web_root: Path | None, keepalive: float | None = 25.0) -> None:
        self._web_root = web_root.resolve() if web_root is not None else None
        self._keepalive = keepalive

    async def accept(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> MessageStream | None:
        """The stream of a new player, or None if the connection was something
        else (a page request, garbage), which has been answered and closed."""
        try:
            first = await reader.readline()
        except (ValueError, OSError):  # a line too long, or the peer vanished
            await self._close(writer)
            return None
        if not first:
            await self._close(writer)
            return None
        if not first.startswith(b"GET "):
            return JsonStream(reader, writer, pending=[first])  # a terminal client
        try:
            headers = await self._read_headers(reader)
        except (ValueError, OSError):
            await self._respond(writer, 400, b"Bad request")
            return None
        path = first.split()[1].decode("latin-1").split("?")[0]
        if headers.get("upgrade", "").lower() == "websocket":
            return await self._upgrade(reader, writer, path, headers)
        await self._serve_file(writer, path)
        return None

    # --- websocket ----------------------------------------------------------

    async def _upgrade(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        path: str,
        headers: dict[str, str],
    ) -> MessageStream | None:
        key = headers.get("sec-websocket-key")
        if path != WEBSOCKET_PATH or key is None:
            await self._respond(writer, 400, b"Bad WebSocket request")
            return None
        writer.write(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {accept_key(key)}\r\n\r\n"
            ).encode("ascii")
        )
        await writer.drain()
        return WebSocketStream(reader, writer, self._keepalive)

    # --- static files -------------------------------------------------------

    async def _serve_file(self, writer: asyncio.StreamWriter, path: str) -> None:
        file = self._find_file(path)
        if file is None:
            await self._respond(writer, 404, b"Not found")
            return
        body = await asyncio.to_thread(file.read_bytes)
        content_type = _CONTENT_TYPES.get(file.suffix, "application/octet-stream")
        await self._respond(writer, 200, body, content_type)

    def _find_file(self, path: str) -> Path | None:
        """The file for a URL path, only if it is inside the web folder."""
        if self._web_root is None:
            return None
        relative = path.lstrip("/") or "index.html"
        file = (self._web_root / relative).resolve()
        if file.is_relative_to(self._web_root) and file.is_file():
            return file
        return None

    # --- http helpers -------------------------------------------------------

    @staticmethod
    async def _read_headers(reader: asyncio.StreamReader) -> dict[str, str]:
        headers: dict[str, str] = {}
        for _ in range(_MAX_HEADERS):
            line = (await reader.readline()).decode("latin-1").strip()
            if not line:
                return headers
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        raise ValueError("too many headers")

    @classmethod
    async def _respond(
        cls,
        writer: asyncio.StreamWriter,
        status: int,
        body: bytes,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        reason = {200: "OK", 400: "Bad Request", 404: "Not Found"}[status]
        head = (
            f"HTTP/1.1 {status} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Cache-Control: no-cache\r\n"
            "Connection: close\r\n\r\n"
        )
        with contextlib.suppress(OSError):
            writer.write(head.encode("ascii") + body)
            await writer.drain()
        await cls._close(writer)

    @staticmethod
    async def _close(writer: asyncio.StreamWriter) -> None:
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
