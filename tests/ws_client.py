"""A WebSocket client for the tests: it behaves like a browser would."""

import asyncio
import base64
import json
import os
import struct
from collections.abc import Mapping
from typing import Any

from src.network.protocol import parse_packet
from src.network.websocket import accept_key, encode_frame


class WsClientStream:
    """A `MessageStream` that talks to the server's WebSocket endpoint."""

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.reader = reader
        self.writer = writer

    @classmethod
    async def connect(cls, port: int, path: str = "/ws") -> "WsClientStream":
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        writer.write(
            (
                f"GET {path} HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n"
                f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode("ascii")
        )
        await writer.drain()
        status = await reader.readline()
        assert status.startswith(b"HTTP/1.1 101"), status
        headers = b""
        while (line := await reader.readline()) not in (b"\r\n", b""):
            headers += line
        assert accept_key(key).encode("ascii") in headers
        return cls(reader, writer)

    # --- raw frames ---------------------------------------------------------

    async def send_frame(self, opcode: int, payload: bytes, fin: bool = True) -> None:
        frame = bytearray(encode_frame(opcode, payload, os.urandom(4)))
        if not fin:
            frame[0] &= 0x7F
        self.writer.write(bytes(frame))
        await self.writer.drain()

    async def read_frame(self) -> tuple[int, bytes]:
        """The next frame from the server, as (opcode, payload)."""
        head = await self.reader.readexactly(2)
        assert not head[1] & 0x80, "servers must not mask"
        length = head[1] & 0x7F
        if length == 126:
            (length,) = struct.unpack("!H", await self.reader.readexactly(2))
        elif length == 127:
            (length,) = struct.unpack("!Q", await self.reader.readexactly(8))
        return head[0] & 0x0F, await self.reader.readexactly(length)

    # --- MessageStream ------------------------------------------------------

    async def send(self, payload: Mapping[str, Any]) -> None:
        await self.send_frame(0x1, json.dumps(payload).encode("utf-8"))

    async def receive(self) -> dict[str, Any]:
        while True:
            try:
                opcode, payload = await self.read_frame()
            except asyncio.IncompleteReadError as error:
                raise ConnectionResetError("closed") from error
            if opcode == 0x1:
                return parse_packet(payload.decode("utf-8"))
            if opcode == 0x8:
                raise ConnectionResetError("closed")

    async def close(self) -> None:
        self.writer.close()
