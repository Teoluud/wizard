"""Plays many seeded games between bots and compares how they score.

python -m src.ai.tournament                          # heuristic vs 2 random
python -m src.ai.tournament --watch 7                # one game, play-by-play
python -m src.ai.tournament --lineup heuristic heuristic random --games 300
"""

import argparse
import asyncio
import math
import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from src.frontend.game_log import GameLog
from src.ai.heuristic_agent import HeuristicAgent, TestHeuristicAgent
from src.ai.random_agent import RandomAgent
from src.backend.agents import PlayerAgent
from src.backend.cards import Deck
from src.backend.game import Game
from src.backend.player import Player

# A bot kind builds a fresh agent for a game, given a seed for its own randomness.
AgentFactory = Callable[[int], PlayerAgent]

KINDS: dict[str, AgentFactory] = {
    "random": lambda seed: RandomAgent(seed),
    "heuristic": lambda seed: HeuristicAgent(),
    "test": lambda seed: TestHeuristicAgent(),
}


@dataclass
class Standing:
    """How all the seats of one kind of bot did over the tournament."""

    kind: str
    points: list[int] = field(
        default_factory=list[int]
    )  # final score, one per seat per game
    wins: float = 0.0  # a tie for first place shares the win

    @property
    def mean(self) -> float:
        return statistics.fmean(self.points)

    @property
    def standard_error(self) -> float:
        if len(self.points) < 2:
            return 0.0
        return statistics.stdev(self.points) / math.sqrt(len(self.points))


def _seat_names(kinds: Sequence[str]) -> list[str]:
    """Unique player names: the kind, numbered when it appears more than once."""
    return [
        f"{kind}-{i + 1}" if kinds.count(kind) > 1 else kind
        for i, kind in enumerate(kinds)
    ]


async def play_game(
    kinds: Sequence[str], seed: int, observers: Sequence[GameLog] = ()
) -> list[Player]:
    """Plays one game with one bot per entry of `kinds`, and returns the players."""
    names = _seat_names(kinds)
    players = [Player(name) for name in names]
    agents = {
        name: KINDS[kind](seed * 100 + i)
        for i, (name, kind) in enumerate(zip(names, kinds))
    }
    await Game(players, Deck(seed), agents, observers).play()
    return players


def seating_for(kinds: Sequence[str], game: int) -> list[str]:
    """The bots in seat order for game number `game`: the seats rotate by one."""
    shift = game % len(kinds)
    return [*kinds[shift:], *kinds[:shift]]


def run_tournament(kinds: Sequence[str], games: int, seed: int = 0) -> list[Standing]:
    """Plays `games` games, rotating the seats so no bot is always in the same one.

    The same `seed` gives the same tournament: game i uses the deck seed `seed + i`.
    """
    standings = {kind: Standing(kind) for kind in dict.fromkeys(kinds)}

    async def run() -> None:
        for game in range(games):
            seating = seating_for(kinds, game)
            players = await play_game(seating, seed + game)
            best = max(p.points for p in players)
            winners = [p for p in players if p.points == best]
            for player, kind in zip(players, seating):
                standings[kind].points.append(player.points)
                if player in winners:
                    standings[kind].wins += 1 / len(winners)

    asyncio.run(run())
    return list(standings.values())


def format_standings(standings: Sequence[Standing], games: int) -> str:
    # align everything
    lines = [
        f"{games} games",
        f"{'bot':<12}{'avg points':>12}{'± error':>10}{'wins':>8}",
    ]
    for s in sorted(standings, key=lambda s: s.mean, reverse=True):
        lines.append(
            f"{s.kind:<12}{s.mean:>12.1f}{s.standard_error:>10.1f}"
            f"{s.wins / games:>8.0%}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare the bots.")
    parser.add_argument(
        "--lineup",
        nargs="+",
        choices=sorted(KINDS),
        default=["heuristic", "random", "random"],
        help="the bot in each seat (default: heuristic random random)",
    )
    parser.add_argument("--games", type=int, default=300)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--watch", type=int, metavar="SEED", help="play one game and print it"
    )
    args = parser.parse_args()

    if args.watch is not None:
        asyncio.run(play_game(args.lineup, args.watch, [GameLog()]))
        return
    standings = run_tournament(args.lineup, args.games, args.seed)
    print(format_standings(standings, args.games))


if __name__ == "__main__":
    main()
