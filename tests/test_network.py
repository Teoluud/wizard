import asyncio
import socket
from collections.abc import Awaitable, Callable

import pytest

from src.ai.random_agent import RandomAgent
from src.backend.agents import PlayerAgent
from src.backend.cards import Card, Color
from src.backend.rules import PassRule
from src.backend.view import PlayerView
from src.network.client import GameClient
from src.network.protocol import JsonStream
from src.network.server import GameServer

TIMEOUT = 60


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class QuittingAgent(RandomAgent):
    """Plays at random, then loses its connection after `answers` answers."""

    def __init__(self, seed: int, answers: int) -> None:
        super().__init__(seed)
        self._left = answers

    def _tick(self) -> None:
        if self._left == 0:
            raise ConnectionResetError("the player closed the window")
        self._left -= 1

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        self._tick()
        return await super().ask_call(view, forbidden_call)

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        self._tick()
        return await super().ask_card(view, legal_cards)

    async def ask_trump_color(self, view: PlayerView) -> Color:
        self._tick()
        return await super().ask_trump_color(view)

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        self._tick()
        return await super().ask_card_to_pass(view, rule, recipient)


async def raw_client(
    port: int, name: str, answer: Callable[[JsonStream], Awaitable[None]] | None
) -> None:
    """A client that joins and then answers every request with `answer`."""
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    stream = JsonStream(reader, writer)
    await stream.send({"kind": "join", "name": name})
    try:
        while True:
            packet = await stream.receive()
            if packet.get("kind") == "request" and answer is not None:
                await answer(stream)
    except (ConnectionError, OSError):
        pass


async def play(
    server: GameServer, port: int, clients: list[Awaitable[None]]
) -> list[BaseException | None]:
    results = await asyncio.wait_for(
        asyncio.gather(server.run(), *clients, return_exceptions=True), TIMEOUT
    )
    return list(results)


def make_server(port: int, humans: int, timeout: float | None = None) -> GameServer:
    return GameServer("127.0.0.1", port, 3, humans, "heuristic", 1, timeout)


async def start(server: GameServer) -> None:
    """Gives the server a moment to start listening."""
    await asyncio.sleep(0.3)


async def agent_client(port: int, name: str, agent: PlayerAgent) -> None:
    await GameClient("127.0.0.1", port, name, agent).run()


def test_a_full_game_with_two_humans_and_a_bot() -> None:
    async def scenario() -> None:
        port = free_port()
        server = make_server(port, humans=2)

        async def clients() -> None:
            await start(server)
            results = await asyncio.gather(
                agent_client(port, "A", RandomAgent(1)),
                agent_client(port, "B", RandomAgent(2)),
                return_exceptions=True,
            )
            assert results == [None, None]

        results = await play(server, port, [clients()])
        assert results == [None, None]
        assert all(r.connected is False for r in server._remote_agents.values())  # type: ignore[reportPrivateUsage]

    asyncio.run(scenario())


def test_a_duplicate_name_is_rejected_and_the_game_still_starts() -> None:
    async def scenario() -> None:
        port = free_port()
        server = make_server(port, humans=2)

        async def clients() -> None:
            await start(server)
            first = asyncio.create_task(agent_client(port, "A", RandomAgent(1)))
            await asyncio.sleep(0.2)
            with pytest.raises(RuntimeError, match="already taken"):
                await agent_client(port, "A", RandomAgent(2))
            await asyncio.gather(first, agent_client(port, "B", RandomAgent(3)))

        results = await play(server, port, [clients()])
        assert results == [None, None]

    asyncio.run(scenario())


def test_a_dropped_player_is_replaced_by_a_bot() -> None:
    async def scenario() -> None:
        port = free_port()
        server = make_server(port, humans=2)

        async def clients() -> None:
            await start(server)
            await asyncio.gather(
                agent_client(port, "Quitter", QuittingAgent(1, answers=6)),
                agent_client(port, "Stayer", RandomAgent(2)),
                return_exceptions=True,
            )

        results = await play(server, port, [clients()])
        assert results[0] is None  # the server finished the game anyway
        assert not server._remote_agents["Quitter"].connected  # type: ignore[reportPrivateUsage]

    asyncio.run(scenario())


def test_garbage_answers_drop_the_player() -> None:
    async def garbage(stream: JsonStream) -> None:
        await stream.send(
            {"kind": "response", "card": {"type": "card", "number": 99, "color": "red"}}
        )

    async def scenario() -> None:
        port = free_port()
        server = make_server(port, humans=1)

        async def clients() -> None:
            await start(server)
            await raw_client(port, "Cheater", garbage)

        results = await play(server, port, [clients()])
        assert results[0] is None
        assert not server._remote_agents["Cheater"].connected  # type: ignore[reportPrivateUsage]

    asyncio.run(scenario())


def test_a_silent_player_is_replaced_after_the_timeout() -> None:
    async def scenario() -> None:
        port = free_port()
        server = make_server(port, humans=1, timeout=0.2)

        async def clients() -> None:
            await start(server)
            await raw_client(port, "Sleeper", None)

        results = await play(server, port, [clients()])
        assert results[0] is None
        assert not server._remote_agents["Sleeper"].connected  # type: ignore[reportPrivateUsage]

    asyncio.run(scenario())
