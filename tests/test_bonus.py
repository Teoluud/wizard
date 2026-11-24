import asyncio

from src.ai.random_agent import RandomAgent
from src.backend.agents import PlayerAgent
from src.backend.bonus import Award, ZeroStreakTracker
from src.backend.cards import Deck
from src.backend.events import BonusAwarded, CallMade, GameEvent, RoundScored, TrickWon
from src.backend.game import Game
from src.backend.player import Player
from src.backend.rules import ZERO_STREAK_BONUS, ZeroStreakBonus
from src.backend.view import PlayerView
from src.network.protocol import JsonCodec
from tests.helpers import EventLog, new_players


def tracker_round(
    tracker: ZeroStreakTracker, number: int, results: dict[str, tuple[int, int]]
) -> list[Award]:
    players: list[Player] = []
    for name, (call, won) in results.items():
        player = Player(name)
        player.call_tricks(call)
        for _ in range(won):
            player.win_trick()
        players.append(player)
    return tracker.record_round(number, players)


def test_the_default_rule_is_four_points_for_six_rounds() -> None:
    assert ZERO_STREAK_BONUS == ZeroStreakBonus(until_round=6, points=4)


def test_a_perfect_streak_is_paid_when_the_sixth_round_ends() -> None:
    tracker = ZeroStreakTracker(ZERO_STREAK_BONUS, ["A", "B"])
    for number in range(1, 6):
        assert tracker_round(tracker, number, {"A": (0, 0), "B": (0, 0)}) == []
    awards = tracker_round(tracker, 6, {"A": (0, 0), "B": (0, 0)})
    assert [(a.player, a.points) for a in awards] == [("A", 4), ("B", 4)]


def test_one_failed_round_loses_the_bonus_for_good() -> None:
    tracker = ZeroStreakTracker(ZERO_STREAK_BONUS, ["A", "B"])
    tracker_round(tracker, 1, {"A": (0, 0), "B": (0, 0)})
    tracker_round(tracker, 2, {"A": (0, 0), "B": (0, 1)})  # B called 0, won 1
    for number in range(3, 6):
        tracker_round(tracker, number, {"A": (0, 0), "B": (0, 0)})
    awards = tracker_round(tracker, 6, {"A": (0, 0), "B": (0, 0)})
    assert [a.player for a in awards] == ["A"]


def test_succeeding_with_another_call_does_not_count() -> None:
    tracker = ZeroStreakTracker(ZERO_STREAK_BONUS, ["A"])
    tracker_round(tracker, 1, {"A": (0, 0)})
    tracker_round(tracker, 2, {"A": (1, 1)})  # a hit, but not a call of 0
    for number in range(3, 6):
        tracker_round(tracker, number, {"A": (0, 0)})
    assert tracker_round(tracker, 6, {"A": (0, 0)}) == []


def test_the_bonus_is_paid_once_at_the_end_of_the_sixth_round() -> None:
    tracker = ZeroStreakTracker(ZERO_STREAK_BONUS, ["A"])
    for number in range(1, 6):
        assert tracker_round(tracker, number, {"A": (0, 0)}) == []
    assert len(tracker_round(tracker, 6, {"A": (0, 0)})) == 1
    assert tracker_round(tracker, 7, {"A": (0, 0)}) == []


class ZeroCaller(RandomAgent):
    """Calls 0 every time and plays at random."""

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        return 0 if forbidden_call != 0 else 1


def run(rule: ZeroStreakBonus | None) -> list[GameEvent]:
    players = new_players()
    agents: dict[str, PlayerAgent] = {
        p.name: ZeroCaller(i) for i, p in enumerate(players)
    }
    log = EventLog()
    game = Game(players, Deck(4), agents, [log], zero_streak=rule)
    asyncio.run(game.play())
    return log.events


def test_the_game_pays_the_bonus_before_the_round_is_scored() -> None:
    # Round 1 has a single trick, so most players succeed with their call of 0.
    events = run(ZeroStreakBonus(until_round=1, points=4))
    end = next(i for i, e in enumerate(events) if isinstance(e, RoundScored))
    first_round = events[:end]
    calls = {e.player: e.call for e in first_round if isinstance(e, CallMade)}
    winner = next(e.winner for e in first_round if isinstance(e, TrickWon))
    expected = {n for n, call in calls.items() if call == 0 and n != winner}
    bonuses = [e for e in first_round if isinstance(e, BonusAwarded)]
    assert {b.player for b in bonuses} == expected and expected
    assert all(b.points == 4 for b in bonuses)

    scored = next(e for e in events if isinstance(e, RoundScored))
    points = {s.name: s.points for s in scored.scores}
    for name in expected:
        assert points[name] == 6  # a total of 6 points are awarded


def test_the_bonus_can_be_switched_off() -> None:
    events = run(None)
    assert not any(isinstance(e, BonusAwarded) for e in events)


def test_the_bonus_event_travels_over_the_network_codec() -> None:
    event = BonusAwarded("A", 6, "called 0 and won no tricks in rounds 1-6")
    assert JsonCodec.decode_event(JsonCodec.encode_event(event)) == event