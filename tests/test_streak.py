import asyncio
from math import isclose

from src.ai.heuristic_agent import HeuristicAgent
from src.ai.knowledge import call_score, expected_score, tricks_distribution
from src.ai.streak import ZeroStreakWatch
from src.backend.events import GameStarted, RoundScored
from src.backend.rules import ZeroStreakBonus
from src.backend.view import PlayerStatus
from tests.test_ai import BLUE, GREEN, RED, card, make_view

RULE = ZeroStreakBonus(until_round=3, points=4)


def scored(number: int, results: dict[str, tuple[int, int]]) -> RoundScored:
    """A RoundScored event; `results` maps a name to (call, tricks won)."""
    return RoundScored(
        number, [PlayerStatus(n, c, w, 0, 0) for n, (c, w) in results.items()]
    )


# --- the odds ------------------------------------------------------------------


def test_tricks_distribution_adds_up_to_one() -> None:
    odds = tricks_distribution([0.2, 0.5, 0.9])
    assert len(odds) == 4
    assert isclose(sum(odds), 1.0)
    assert isclose(odds[0], 0.8 * 0.5 * 0.1)
    assert isclose(odds[3], 0.2 * 0.5 * 0.9)


def test_tricks_distribution_without_tricks_is_a_sure_zero() -> None:
    assert tricks_distribution([]) == [1.0]


def test_call_score_follows_the_scoring_rules() -> None:
    assert call_score(2, 2) == 4
    assert call_score(0, 0) == 2
    assert call_score(1, 3) == -2


def test_expected_score_weighs_every_result() -> None:
    # 0 tricks with 75%, 1 trick with 25%
    assert isclose(expected_score(0, [0.75, 0.25]), 0.75 * 2 - 0.25)


# --- following the streaks -----------------------------------------------------


def test_a_player_who_breaks_the_streak_stays_out() -> None:
    watch = ZeroStreakWatch(RULE)
    watch.on_event(scored(1, {"A": (0, 0), "B": (1, 1), "C": (0, 1)}))
    assert watch.is_alive("A")
    assert not watch.is_alive("B")  # called 1
    assert not watch.is_alive("C")  # called 0 but won a trick


def test_rounds_after_the_streak_do_not_count() -> None:
    watch = ZeroStreakWatch(RULE)
    watch.on_event(scored(4, {"A": (2, 0)}))
    assert watch.is_alive("A")


def test_a_new_game_gives_everybody_a_fresh_streak() -> None:
    watch = ZeroStreakWatch(RULE)
    watch.on_event(scored(1, {"A": (1, 1)}))
    watch.on_event(GameStarted(["A", "B", "C"], 20))
    assert watch.is_alive("A")


def test_without_the_rule_nobody_has_a_streak() -> None:
    watch = ZeroStreakWatch(None)
    assert not watch.is_alive("A")
    assert watch.zero_bonus("A", 1) == 0.0


def test_the_bonus_is_worth_more_the_closer_the_end_of_the_streak() -> None:
    watch = ZeroStreakWatch(RULE)
    assert watch.zero_bonus("A", 3) == 4.0
    assert watch.zero_bonus("A", 2) < watch.zero_bonus("A", 3)
    assert watch.zero_bonus("A", 1) < watch.zero_bonus("A", 2)
    assert watch.zero_bonus("A", 4) == 0.0


# --- the bot -------------------------------------------------------------------


def test_a_bot_on_a_streak_calls_the_0_it_would_otherwise_skip() -> None:
    hand = [card(BLUE, 9), card(RED, 9)]
    view = make_view(hand, round_number=2, trump=card(GREEN, 5))
    assert asyncio.run(HeuristicAgent(None).ask_call(view, None)) == 1
    assert asyncio.run(HeuristicAgent().ask_call(view, None)) == 0


def test_a_bot_that_broke_its_streak_calls_as_usual() -> None:
    hand = [card(BLUE, 9), card(RED, 9)]
    view = make_view(hand, round_number=2, trump=card(GREEN, 5))
    bot = HeuristicAgent()
    asyncio.run(bot.on_event(scored(1, {"A": (1, 1)})))
    assert asyncio.run(bot.ask_call(view, None)) == 1


def test_a_bot_does_not_give_up_a_good_call_for_the_bonus() -> None:
    hand = [card(RED, 13), card(BLUE, 13)]
    view = make_view(hand, round_number=2, trump=card(RED, 5))
    assert asyncio.run(HeuristicAgent().ask_call(view, None)) > 0


def test_the_bot_still_respects_the_forbidden_call() -> None:
    hand = [card(BLUE, 9), card(RED, 9)]
    view = make_view(hand, round_number=2, trump=card(GREEN, 5))
    assert asyncio.run(HeuristicAgent().ask_call(view, 0)) == 1