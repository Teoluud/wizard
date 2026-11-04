import asyncio
import json
import socket
import struct
from collections.abc import Awaitable, Callable
from pathlib import Path

from src.ai.random_agent import RandomAgent
from src.network.client import GameClient
from src.network.gateway import Gateway
from src.network.protocol import JsonStream, MessageStream
from src.network.server import GameServer
from src.network.websocket import accept_key, encode_frame
from tests.ws_client import WsClientStream


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def with_gateway(
    web_root: Path | None,
    scenario: Callable[[int], Awaitable[None]],
    keepalive: float | None = None,
) -> None:
    """Runs `scenario(port)` against a server that echoes every packet."""
    gateway = Gateway(web_root, keepalive)

    async def handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        stream = await gateway.accept(reader, writer)
        if stream is None:
            return
        try:
            while True:
                await stream.send(await stream.receive())
        except (OSError, ValueError):
            await stream.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])
    async with server:
        await asyncio.wait_for(scenario(port), 10)


async def http_get(port: int, path: str) -> tuple[int, dict[str, str], bytes]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: x\r\n\r\n".encode("ascii"))
    await writer.drain()
    status = int((await reader.readline()).split()[1])
    headers: dict[str, str] = {}
    while (line := (await reader.readline()).strip()) != b"":
        name, _, value = line.decode("latin-1").partition(":")
        headers[name.lower()] = value.strip()
    body = await reader.readexactly(int(headers["content-length"]))
    writer.close()
    return status, headers, body


def test_the_accept_key_matches_the_rfc_example() -> None:
    assert accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_frames_use_the_right_length_encoding() -> None:
    assert encode_frame(0x1, b"hi") == b"\x81\x02hi"
    assert encode_frame(0x1, b"x" * 200)[:4] == b"\x81\x7e\x00\xc8"
    assert encode_frame(0x1, b"x" * 70000)[:2] == b"\x81\x7f"
    masked = encode_frame(0x1, b"hi", b"\x01\x02\x03\x04")
    assert masked == b"\x81\x82\x01\x02\x03\x04" + bytes([ord("h") ^ 1, ord("i") ^ 2])


def test_it_serves_the_files_of_the_web_folder(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    (tmp_path / "app.js").write_text("export {}")
    (tmp_path.parent / "secret.txt").write_text("secret")

    async def scenario(port: int) -> None:
        status, headers, body = await http_get(port, "/")
        assert (status, body) == (200, b"<h1>hi</h1>")
        assert headers["content-type"].startswith("text/html")
        _, headers, _ = await http_get(port, "/app.js")
        assert headers["content-type"].startswith("text/javascript")
        assert (await http_get(port, "/missing.html"))[0] == 404
        assert (await http_get(port, "/../secret.txt"))[0] == 404
        assert (await http_get(port, "/%2e%2e/secret.txt"))[0] == 404

    asyncio.run(with_gateway(tmp_path, scenario))


def test_without_a_web_folder_pages_are_not_found() -> None:
    async def scenario(port: int) -> None:
        assert (await http_get(port, "/"))[0] == 404

    asyncio.run(with_gateway(None, scenario))


def test_a_websocket_echoes_packets_and_answers_pings() -> None:
    async def scenario(port: int) -> None:
        ws = await WsClientStream.connect(port)
        await ws.send({"kind": "join", "name": "Ünï"})
        assert await ws.receive() == {"kind": "join", "name": "Ünï"}
        await ws.send_frame(0x9, b"are you there")
        assert await ws.read_frame() == (0xA, b"are you there")
        await ws.close()

    asyncio.run(with_gateway(None, scenario))


def test_a_message_split_in_fragments_is_put_together() -> None:
    async def scenario(port: int) -> None:
        ws = await WsClientStream.connect(port)
        text = json.dumps({"kind": "x", "data": "y" * 300}).encode("utf-8")
        await ws.send_frame(0x1, text[:100], fin=False)
        await ws.send_frame(0x9, b"ping in the middle")
        await ws.send_frame(0x0, text[100:200], fin=False)
        await ws.send_frame(0x0, text[200:])
        assert await ws.read_frame() == (0xA, b"ping in the middle")
        assert (await ws.receive())["data"] == "y" * 300
        await ws.close()

    asyncio.run(with_gateway(None, scenario))


def test_a_close_is_answered_with_a_close() -> None:
    async def scenario(port: int) -> None:
        ws = await WsClientStream.connect(port)
        await ws.send_frame(0x8, struct.pack("!H", 1000))
        opcode, _ = await ws.read_frame()
        assert opcode == 0x8
        assert await ws.reader.read() == b""  # and then the server hangs up

    asyncio.run(with_gateway(None, scenario))


def test_broken_clients_are_closed_with_an_error() -> None:
    async def expect_close(
        port: int, send: Callable[[WsClientStream], Awaitable[None]]
    ) -> None:
        ws = await WsClientStream.connect(port)
        await send(ws)
        opcode, payload = await ws.read_frame()
        assert opcode == 0x8
        assert struct.unpack("!H", payload[:2])[0] != 1000
        await ws.close()

    async def unmasked(ws: WsClientStream) -> None:
        ws.writer.write(encode_frame(0x1, b"{}"))  # clients must mask
        await ws.writer.drain()

    async def binary(ws: WsClientStream) -> None:
        await ws.send_frame(0x2, b"\x00\x01")

    async def orphan_continuation(ws: WsClientStream) -> None:
        await ws.send_frame(0x0, b"{}")

    async def not_an_object(ws: WsClientStream) -> None:
        await ws.send_frame(0x1, b"[1, 2]")

    async def scenario(port: int) -> None:
        await expect_close(port, unmasked)
        await expect_close(port, binary)
        await expect_close(port, orphan_continuation)
        ws = await WsClientStream.connect(port)
        await not_an_object(ws)
        assert (await ws.read_frame())[0] == 0x8  # not a JSON object: hang up
        assert await ws.reader.read() == b""

    asyncio.run(with_gateway(None, scenario))


def test_the_server_pings_to_keep_the_connection_alive() -> None:
    async def scenario(port: int) -> None:
        ws = await WsClientStream.connect(port)
        assert (await ws.read_frame())[0] == 0x9
        await ws.close()

    asyncio.run(with_gateway(None, scenario, keepalive=0.1))


def test_a_terminal_client_still_gets_in_through_the_gateway() -> None:
    async def scenario(port: int) -> None:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        stream: MessageStream = JsonStream(reader, writer)
        await stream.send({"kind": "join", "name": "T"})
        assert await stream.receive() == {"kind": "join", "name": "T"}
        await stream.close()

    asyncio.run(with_gateway(None, scenario))


def test_a_browser_and_a_terminal_player_can_share_a_table() -> None:
    async def scenario() -> None:
        port = free_port()
        server = GameServer("127.0.0.1", port, 3, 2, "heuristic", 1)

        async def browser() -> None:
            await asyncio.sleep(0.3)
            ws = await WsClientStream.connect(port)
            await GameClient("", port, "Web", RandomAgent(1)).play(ws)

        async def terminal() -> None:
            await asyncio.sleep(0.4)
            await GameClient("127.0.0.1", port, "Tty", RandomAgent(2)).run()

        results = await asyncio.wait_for(
            asyncio.gather(server.run(), browser(), terminal()), 60
        )
        assert results == [None, None, None]
        assert not any(r.connected for r in server.humans.values())

    asyncio.run(scenario())
