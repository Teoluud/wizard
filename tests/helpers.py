import asyncio
from collections.abc import Callable, Mapping

from src.ai.random_agent import RandomAgent
from src.backend.agents import PlayerAgent
from src.backend.cards import Card, Color, Deck
from src.backend.events import GameEvent
from src.backend.game import Game
from src.backend.player import Player
from src.backend.round import Round
from src.backend.rules import PassRule, rules_for
from src.backend.view import PlayerView

NAMES = ("A", "B", "C")


class SpyAgent(RandomAgent):
    """A RandomAgent that remembers every question and the view it was given."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.asked: list[tuple[str, PlayerView]] = []

    async def ask_trump_color(self, view: PlayerView) -> Color:
        self.asked.append(("trump", view))
        return await super().ask_trump_color(view)

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        self.asked.append(("call", view))
        return await super().ask_call(view, forbidden_call)

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        self.asked.append(("pass", view))
        return await super().ask_card_to_pass(view, rule, recipient)

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        self.asked.append(("card", view))
        return await super().ask_card(view, legal_cards)


class EventLog:
    """An observer that just keeps every event."""

    def __init__(self) -> None:
        self.events: list[GameEvent] = []

    async def on_event(self, event: GameEvent) -> None:
        self.events.append(event)


def new_players() -> list[Player]:
    return [Player(name) for name in NAMES]


def run_game(
    seed: int, agents: Mapping[str, PlayerAgent] | None = None
) -> list[GameEvent]:
    """Plays a whole game and returns every event, in order."""
    players = new_players()
    if agents is None:
        agents = {p.name: RandomAgent(seed * 10 + i) for i, p in enumerate(players)}
    log = EventLog()
    asyncio.run(Game(players, Deck(seed), agents, [log]).play())
    return log.events


def make_round(
    number: int, seed: int = 0, choose_trump: bool = True
) -> tuple[Round, list[Player]]:
    """A started round. A Wizard trump gets its suit picked (red) if asked to."""
    players = new_players()
    round_ = Round(list(players), Deck(seed), number, rules_for(number))
    round_.start()
    if choose_trump and round_.needs_trump_choice:
        round_.choose_trump_color(Color.RED)
    return round_, players


def find_round(
    number: int, wanted: Callable[[Card | None], bool], choose_trump: bool = True
) -> tuple[Round, list[Player]]:
    """A started round whose trump card satisfies `wanted` (tries seeds 0, 1, ...)."""
    for seed in range(1000):
        round_, players = make_round(number, seed, choose_trump=False)
        if wanted(round_.trump_card):
            if choose_trump and round_.needs_trump_choice:
                round_.choose_trump_color(Color.RED)
            return round_, players
    raise AssertionError("no seed gives the wanted trump card")


def call_all(round_: Round) -> None:
    """Everybody calls the lowest number they are allowed to."""
    for player in round_.players:
        forbidden = round_.forbidden_call(player)
        call = next(c for c in range(round_.number + 1) if c != forbidden)
        round_.set_call(player, call)
