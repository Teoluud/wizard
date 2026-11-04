"""A small WebSocket (RFC 6455) layer on top of asyncio streams.

Only what the game needs: the opening handshake, text messages (also when the
peer splits them in fragments), ping/pong and closing. No extensions.
"""

import asyncio
import base64
import contextlib
import hashlib
import json
import struct
from collections.abc import Mapping
from typing import Any

from src.network.protocol import parse_packet

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_MESSAGE = 1 << 20  # 1 MiB: far more than any packet of the game

_CONTINUATION, _TEXT, _BINARY = 0x0, 0x1, 0x2

_CLOSE, _PING, _PONG = 0x8, 0x9, 0xA

# Status codes for the close frame.
_NORMAL, _PROTOCOL_ERROR, _BAD_DATA, _TOO_BIG = 1000, 1002, 1003, 1009


def accept_key(client_key: str) -> str:
    """The `Sec-WebSocket-Accept` value that answers a client's key."""
    digest = hashlib.sha1((client_key + _GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_frame(opcode: int, payload: bytes, mask: bytes | None = None) -> bytes:
    """One complete (FIN) frame. Servers don't mask; clients must (`mask`)."""
    first = 0x80 | opcode
    length = len(payload)
    mask_bit = 0x80 if mask is not None else 0
    if length < 126:
        header = struct.pack("!BB", first, mask_bit | length)
    elif length < 1 << 16:
        header = struct.pack("!BBH", first, mask_bit | 126, length)
    else:
        header = struct.pack("!BBQ", first, mask_bit | 127, length)
    if mask is None:
        return header + payload
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return header + mask + masked


class WebSocketStream:
    """A `MessageStream` over a WebSocket whose handshake is already done."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        keepalive: float | None = 25.0
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._closed = False
        # Tunnels and proxies idle connections: ping while a human thinks.
        self._pinger = (
            asyncio.create_task(self._ping_forever(keepalive))
            if keepalive is not None
            else None
        )

    async def send(self, payload: Mapping[str, Any]) -> None:
        await self._write(encode_frame(_TEXT, json.dumps(payload).encode("utf-8")))

    async def receive(self) -> dict[str, Any]:
        """The next text message, answering pings and the close on the way."""
        text = bytearray()
        started = False
        while True:
            fin, opcode, payload = await self._read_frame()
            if opcode == _PING:
                await self._write(encode_frame(_PONG, payload))
            elif opcode == _PONG:
                continue
            elif opcode == _CLOSE:
                await self._reply_to_close()
                raise ConnectionResetError("The peer closed the WebSocket.")
            elif opcode in (_TEXT, _CONTINUATION):
                if (opcode == _TEXT) == started:
                    await self._fail(_PROTOCOL_ERROR, "unexpected frame order")
                started = True
                text += payload
                if len(text) > _MAX_MESSAGE:
                    await self._fail(_TOO_BIG, "message too big")
                if fin:
                    try:
                        return parse_packet(text.decode("utf-8"))
                    except UnicodeDecodeError as error:
                        await self._fail(_BAD_DATA, "invalid UTF-8")
                        raise ValueError("invalid UTF-8") from error
            else:
                await self._fail(_BAD_DATA, "only text messages are supported")

    async def close(self) -> None:
        """Says goodbye and closes; a peer that is already gone is not an error."""
        if self._pinger is not None:
            self._pinger.cancel()
        if not self._closed:
            self._closed = True
            with contextlib.suppress(OSError):
                self._writer.write(encode_frame(_CLOSE, struct.pack("!H", _NORMAL)))
                await self._writer.drain()
        self._writer.close()
        with contextlib.suppress(OSError):
            await self._writer.wait_closed()

    # --- frames -------------------------------------------------------------

    async def _read_frame(self) -> tuple[bool, int, bytes]:
        try:
            head = await self._reader.readexactly(2)
            fin = bool(head[0] & 0x80)
            opcode = head[0] & 0x0F
            masked = bool(head[1] & 0x80)
            length = head[1] & 0x7F
            if length == 126:
                (length,) = struct.unpack("!H", await self._reader.readexactly(2))
            elif length == 127:
                (length,) = struct.unpack("!Q", await self._reader.readexactly(8))
            if head[0] & 0x70 or not masked:
                await self._fail(_PROTOCOL_ERROR, "bad frame header")
            if length > _MAX_MESSAGE or (opcode >= _CLOSE and length > 125):
                await self._fail(_TOO_BIG, "frame too big")
            mask = await self._reader.readexactly(4)
            data = await self._reader.readexactly(length)
        except asyncio.IncompleteReadError as error:
            raise ConnectionResetError("The peer closed the connection.") from error
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
        if opcode >= _CLOSE and not fin:
            await self._fail(_PROTOCOL_ERROR, "fragmented control frame")
        return fin, opcode, payload

    async def _write(self, frame: bytes) -> None:
        if self._closed:
            raise ConnectionError("The WebSocket is closed.")
        self._writer.write(frame)
        await self._writer.drain()

    async def _reply_to_close(self) -> None:
        if not self._closed:
            self._closed = True
            with contextlib.suppress(OSError):
                self._writer.write(encode_frame(_CLOSE, struct.pack("!H", _NORMAL)))
                await self._writer.drain()

    async def _fail(self, code: int, reason: str) -> None:
        """Closes with an error code and raises: the peer broke the protocol."""
        if not self._closed:
            self._closed = True
            with contextlib.suppress(OSError):
                body = struct.pack("!H", code) + reason.encode("utf-8")
                self._writer.write(encode_frame(_CLOSE, body))
                await self._writer.drain()
        raise ValueError(f"WebSocket protocol error: {reason}")

    async def _ping_forever(self, interval: float) -> None:
        with contextlib.suppress(OSError):
            while not self._closed:
                await asyncio.sleep(interval)
                await self._write(encode_frame(_PING, b""))