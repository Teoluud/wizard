"""Authoritative Wizard server.

Example (3-player game with 1 human and 2 heuristic bots):
    python -m src.network.server --seats 3 --humans 1 --bot heuristic
"""

import argparse
import asyncio
import random

from src.ai.tournament import KINDS
from src.frontend.game_log import GameLog
from src.backend.agents import PlayerAgent
from src.backend.cards import Deck
from src.backend.game import Game
from src.backend.player import Player
from src.network.protocol import JsonStream
from src.network.remote_agent import RemotePlayerAgent


class GameServer:
    """Accepts client connections, fills empty seats with bots, and runs Game."""

    def __init__(
        self,
        host: str,
        port: int,
        seats: int,
        expected_humans: int,
        bot_kind: str = "heuristic",
        seed: int | None = None,
    ) -> None:
        if not 2 <= seats <= 6:
            raise ValueError("Wizard requires between 2 and 6 seats.")
        if not 0 <= expected_humans <= seats:
            raise ValueError("expected_humans must be between 0 and seats.")
        if bot_kind not in KINDS:
            raise ValueError(f"Unknown bot kind: {bot_kind}")

        self.host = host
        self.port = port
        self.seats = seats
        self.expected_humans = expected_humans
        self.bot_kind = bot_kind
        self.seed = seed

        self._remote_agents: dict[str, RemotePlayerAgent] = {}
        self._lobby_ready = asyncio.Event()
        if expected_humans == 0:
            self._lobby_ready.set()

    async def run(self) -> None:
        server = await asyncio.start_server(self._handle_client, self.host, self.port)
        print(
            f"Listening on {self.host}:{self.port} - waiting for "
            f"{self.expected_humans} human player(s) ({self.seats} total seats)..."
        )
        async with server:
            await self._lobby_ready.wait()
            players, agents = self._build_table()
            print("Table ready: " + ", ".join(p.name for p in players))
            game = Game(players, Deck(self.seed), agents, observers=[GameLog()])
            try:
                await game.play()
            finally:
                for remote in self._remote_agents.values():
                    await remote.close()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        stream = JsonStream(reader, writer)
        try:
            hello = await stream.receive()
        except (ConnectionResetError, ValueError):
            await stream.close()
            return

        name = str(hello.get("name", "")).strip()
        problem = self._join_problem(hello.get("kind"), name)
        if problem is not None:
            await stream.send({"kind": "error", "message": problem})
            await stream.close()
            return

        # No awaits between the checks above and this line, so two clients can't race.
        self._remote_agents[name] = RemotePlayerAgent(name, stream)
        await stream.send(
            {
                "kind": "welcome",
                "message": (
                    f"Joined as {name} "
                    f"({len(self._remote_agents)}/{self.expected_humans} humans)."
                ),
            }
        )
        print(
            f"Player '{name}' connected "
            f"({len(self._remote_agents)}/{self.expected_humans})."
        )
        if len(self._remote_agents) == self.expected_humans:
            self._lobby_ready.set()

    def _join_problem(self, kind: object, name: str) -> str | None:
        if kind != "join" or not name:
            return "Expected a join packet with a name."
        if len(self._remote_agents) >= self.expected_humans:
            return "Lobby is already full."
        if name in self._remote_agents:
            return f"The name '{name}' is already taken."
        return None

    def _build_table(self) -> tuple[list[Player], dict[str, PlayerAgent]]:
        """Builds a table of players and their respective agents."""
        players: list[Player] = []
        agents: dict[str, PlayerAgent] = {}

        for name, remote in self._remote_agents.items():
            players.append(Player(name))
            agents[name] = remote

        bots_needed = self.seats - len(players)
        base_seed = self.seed or 0
        for i in range(1, bots_needed + 1):
            bot_name = f"{self.bot_kind}-{i}"
            while bot_name in agents:
                i += 1
                bot_name = f"{self.bot_kind}-{i}"
            players.append(Player(bot_name))
            agents[bot_name] = KINDS[self.bot_kind](base_seed * 100 + i)
        # Avoid humans always getting the first seats
        random.shuffle(players)
        return players, agents


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Wizard game server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--seats", type=int, default=3, help="total seats at the table (2-6)"
    )
    parser.add_argument(
        "--humans",
        type=int,
        default=1,
        help="number of remote human players to wait for",
    )
    parser.add_argument(
        "--bot",
        choices=sorted(KINDS),
        default="heuristic",
        help="bot kind used to fill empty seats",
    )
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    server = GameServer(
        host=args.host,
        port=args.port,
        seats=args.seats,
        expected_humans=args.humans,
        bot_kind=args.bot,
        seed=args.seed,
    )
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
