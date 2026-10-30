import asyncio

import pytest

from src.ai.random_agent import RandomAgent
from src.backend.cards import Deck, Jester, Wizard
from src.backend.events import (
    CallMade,
    CardPlayed,
    CardsPassed,
    GameEvent,
    GameOver,
    GameStarted,
    RoundScored,
    RoundStarted,
    TrickWon,
    TrumpChosen,
)
from src.backend.game import Game, InvalidMoveError
from src.backend.player import Player
from src.backend.rules import Direction
from src.backend.view import PlayerView
from tests.helpers import (
    NAMES,
    EventLog,
    SpyAgent,
    new_players,
    run_game,
)

N_ROUNDS = 20  # 60 cards / 3 players


def split_rounds(events: list[GameEvent]) -> list[list[GameEvent]]:
    """The events of each round, in order."""
    rounds: list[list[GameEvent]] = []
    for event in events:
        if isinstance(event, RoundStarted):
            rounds.append([])
        if rounds:
            rounds[-1].append(event)
    return rounds


def count(events: list[GameEvent], kind: type) -> int:
    return sum(isinstance(e, kind) for e in events)


def test_a_game_goes_from_start_to_game_over() -> None:
    events = run_game(seed=1)
    assert events[0] == GameStarted(list(NAMES), N_ROUNDS)
    assert isinstance(events[-1], GameOver)
    assert sorted(s.name for s in events[-1].scores) == sorted(NAMES)
    assert len(split_rounds(events)) == N_ROUNDS


def test_every_round_is_played_completely() -> None:
    for number, events in enumerate(split_rounds(run_game(seed=2)), start=1):
        assert count(events, CallMade) == 3
        assert count(events, CardPlayed) == 3 * number
        assert count(events, TrickWon) == number
        assert count(events, RoundScored) == 1


def test_the_tricks_won_add_up_to_the_cards_in_hand() -> None:
    for number, events in enumerate(split_rounds(run_game(seed=3)), start=1):
        scored = next(e for e in events if isinstance(e, RoundScored))
        assert sum(s.tricks_won for s in scored.scores) == number


def test_the_dealer_never_makes_the_calls_add_up_to_the_tricks() -> None:
    for seed in range(10):
        for number, events in enumerate(split_rounds(run_game(seed)), start=1):
            calls = [e.call for e in events if isinstance(e, CallMade)]
            assert sum(calls) != number


def test_the_dealer_picks_the_suit_exactly_when_the_trump_is_a_wizard() -> None:
    wizard_rounds = 0
    for events in split_rounds(run_game(seed=4)):
        started = events[0]
        assert isinstance(started, RoundStarted)
        is_wizard = isinstance(started.trump.card, Wizard)
        chosen = [e for e in events if isinstance(e, TrumpChosen)]
        assert len(chosen) == (1 if is_wizard else 0)
        if is_wizard:
            wizard_rounds += 1
            assert chosen[0].dealer == started.dealer
        elif isinstance(started.trump.card, Jester):
            assert started.trump.color is None
    assert wizard_rounds > 0, "this seed should exercise the Wizard trump"


def test_cards_are_only_passed_in_rounds_8_and_9() -> None:
    for number, events in enumerate(split_rounds(run_game(seed=5)), start=1):
        passed = [e for e in events if isinstance(e, CardsPassed)]
        if number == 8:
            assert passed == [CardsPassed(2, Direction.RIGHT)]
        elif number == 9:
            assert passed == [CardsPassed(2, Direction.LEFT)]
        else:
            assert passed == []


def test_points_follow_the_scoring_rule_round_after_round() -> None:
    previous = {name: 0 for name in NAMES}
    for events in split_rounds(run_game(seed=6)):
        scored = next(e for e in events if isinstance(e, RoundScored))
        for status in scored.scores:
            assert status.call is not None
            if status.tricks_won == status.call:
                gained = status.call + 2
            else:
                gained = -abs(status.call - status.tricks_won)
            assert status.points == previous[status.name] + gained
            previous[status.name] = status.points


def test_the_same_seed_replays_the_same_game() -> None:
    assert run_game(seed=7) == run_game(seed=7)
    assert run_game(seed=7) != run_game(seed=8)


def test_every_agent_only_gets_the_view_it_is_allowed_to_see() -> None:
    spies = {name: SpyAgent(i) for i, name in enumerate(NAMES)}
    run_game(seed=9, agents=spies)

    for name, spy in spies.items():
        assert spy.asked, "every seat should have been asked something"
        for kind, view in spy.asked:
            assert view.player_name == name
            owners = [owner for owner, _ in view.hands]
            if view.round_number == 1 and kind != "pass":
                # Blind round: everybody else's cards, never your own.
                assert view.own_hand is None
                assert name not in owners
            elif view.round_number == 6 and kind in ("trump", "call"):
                assert view.hands == []
            else:
                assert owners == [name]
            if kind == "pass":
                assert view.round_number in (8, 9)
                assert view.own_hand is not None
                assert len(view.own_hand) == view.round_number


class CarelessAgent(RandomAgent):
    """Tries the forbidden call first, and only then plays by the rules."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.tried: set[int] = set()
        self.cheats = 0

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        if forbidden_call is not None and view.round_number not in self.tried:
            self.tried.add(view.round_number)
            self.cheats += 1
            return forbidden_call
        return await super().ask_call(view, forbidden_call)


class StubbornAgent(RandomAgent):
    """Always insists on the forbidden call."""

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        return forbidden_call if forbidden_call is not None else 0


def test_an_answer_the_rules_reject_is_asked_again() -> None:
    careless = CarelessAgent(0)
    agents = {"A": careless, "B": RandomAgent(1), "C": RandomAgent(2)}
    events = run_game(seed=10, agents=agents)

    assert careless.cheats > 0
    for number, round_events in enumerate(split_rounds(events), start=1):
        calls = [e.call for e in round_events if isinstance(e, CallMade)]
        assert sum(calls) != number


def test_an_agent_that_never_plays_by_the_rules_stops_the_game() -> None:
    agents = {"A": StubbornAgent(0), "B": RandomAgent(1), "C": RandomAgent(2)}
    with pytest.raises(InvalidMoveError):
        run_game(seed=11, agents=agents)


def test_names_must_be_unique() -> None:
    players = [Player("A"), Player("A"), Player("C")]
    agents = {name: RandomAgent(0) for name in NAMES}
    with pytest.raises(ValueError):
        Game(players, Deck(0), agents)


def test_every_player_needs_an_agent() -> None:
    agents = {"A": RandomAgent(0), "B": RandomAgent(1)}
    with pytest.raises(ValueError):
        Game(new_players(), Deck(0), agents)


def test_observers_all_see_every_event() -> None:
    first, second = EventLog(), EventLog()
    agents = {name: RandomAgent(i) for i, name in enumerate(NAMES)}
    game = Game(new_players(), Deck(12), agents, [first, second])
    asyncio.run(game.play())
    assert first.events == second.events
    assert len(first.events) > 0


class CountingAgent(RandomAgent):
    """A player that is also an observer, like the CLI or a bot that counts cards."""

    def __init__(self, seed: int) -> None:
        super().__init__(seed)
        self.events: list[GameEvent] = []

    async def on_event(self, event: GameEvent) -> None:
        self.events.append(event)


def test_an_agent_that_is_also_an_observer_gets_every_event_exactly_once() -> None:
    log = EventLog()
    shared = CountingAgent(0)  # the same object sits at all three seats
    agents = {name: shared for name in NAMES}
    # Listing it as an observer too must not make it receive the events twice.
    game = Game(new_players(), Deck(13), agents, [log, shared])
    asyncio.run(game.play())
    assert shared.events == log.events


def test_agents_that_are_not_observers_are_left_alone() -> None:
    log = EventLog()
    agents = {name: RandomAgent(i) for i, name in enumerate(NAMES)}
    game = Game(new_players(), Deck(14), agents, [log])
    assert game.observers == [log]


def test_an_observing_agent_is_registered_without_being_listed() -> None:
    log = EventLog()
    shared = CountingAgent(0)
    game = Game(new_players(), Deck(15), {name: shared for name in NAMES}, [log])
    asyncio.run(game.play())
    assert shared.events == log.events and len(log.events) > 0
