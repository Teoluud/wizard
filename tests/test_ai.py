import asyncio
from random import Random

from src.ai.heuristic_agent import HeuristicAgent
from src.ai.knowledge import (
    beats,
    blind_win_chance,
    expected_tricks,
    hold_chance,
    trick_winner,
    unseen_cards,
)
from src.ai.random_agent import RandomAgent
from src.ai.tournament import format_standings, run_tournament, seating_for
from src.backend.agents import PlayerAgent
from src.backend.cards import Card, Color, Deck, Jester, Wizard
from src.backend.events import CardPlayed, GameEvent, RoundStarted
from src.backend.player import Player
from src.backend.rules import Direction, PassRule
from src.backend.trick import Trick
from src.backend.view import PlayerStatus, PlayerView, Trump
from tests.helpers import NAMES, run_game

RED, BLUE, GREEN, YELLOW = Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW


def card(color: Color, number: int) -> Card:
    return Card(color=color, number=number)


def make_view(
    hand: list[Card] | None,
    table: list[tuple[str, Card]] | None = None,
    call: int = 1,
    tricks_won: int = 0,
    trump: Card | None = None,
    me: str = "A",
    order: tuple[str, ...] = ("B", "C", "A"),
    others: dict[str, list[Card]] | None = None,
    round_number: int | None = None,
) -> PlayerView:
    """A view for `me`, who sits in the position given by `order`."""
    hands = [(me, hand)] if hand is not None else []
    hands += list((others or {}).items())
    return PlayerView(
        player_name=me,
        round_number=round_number or len(hand or [1]),
        dealer_name=order[-1],
        trump=Trump(trump, trump.color if trump else None),
        players=[
            PlayerStatus(
                name, call if name == me else None, tricks_won if name == me else 0, 0, 3
            )
            for name in order
        ],
        hands=hands,
        table=table or [],
    )


# --- shared card knowledge ---------------------------------------------------


def test_unseen_cards_counts_equal_cards_one_by_one() -> None:
    unseen = unseen_cards([Wizard(), card(RED, 5)])
    assert len(unseen) == 58
    assert sum(isinstance(c, Wizard) for c in unseen) == 3
    assert card(RED, 5) not in unseen


def test_who_beats_whom() -> None:
    assert beats(Wizard(), card(RED, 13), GREEN)
    assert not beats(Wizard(), Wizard(), GREEN)  # the first Wizard wins
    assert not beats(card(RED, 13), Wizard(), GREEN)
    assert not beats(Jester(), card(RED, 1), GREEN)
    assert beats(card(RED, 1), Jester(), GREEN)
    assert beats(card(RED, 9), card(RED, 5), None)
    assert not beats(card(RED, 5), card(RED, 9), None)
    assert beats(card(GREEN, 1), card(RED, 13), GREEN)  # trump beats any other suit
    assert not beats(card(BLUE, 13), card(RED, 1), GREEN)  # other suits never do


def test_trick_winner_agrees_with_the_real_trick() -> None:
    rng = Random(0)
    for _ in range(3000):
        cards = Deck(rng.randrange(10**9)).cards[: rng.choice([3, 3, 4])]
        trump = rng.choice([None, *Color])
        players = [Player(f"P{i}") for i in range(len(cards))]
        trick = Trick(players, trump)
        for player, played in zip(players, cards):
            trick.add_play(player, played)
        plays = [(p.name, c) for p, c in zip(players, cards)]
        assert trick_winner(plays, trump) == trick.winner().name


def test_sure_winners_and_sure_losers() -> None:
    unseen = unseen_cards([])
    assert hold_chance(Wizard(), unseen, GREEN, 2) == 1.0
    assert hold_chance(Jester(), unseen, GREEN, 0) == 1.0  # nobody left to beat it
    assert hold_chance(card(RED, 13), unseen, None, 2) > hold_chance(
        card(RED, 2), unseen, None, 2
    )


def test_an_average_hand_is_worth_its_fair_share_of_tricks() -> None:
    rng = Random(1)
    for n in (3, 8, 15):
        total = 0.0
        for _ in range(300):
            deck = Deck(rng.randrange(10**9)).cards
            hand, trump_card = deck[:n], deck[3 * n]
            unseen = unseen_cards([*hand, trump_card])
            total += expected_tricks(hand, unseen, trump_card.color, 2)
        assert abs(total / 300 - n / 3) < 0.1 * n / 3


def test_round_one_win_chance_uses_the_visible_cards() -> None:
    # Playing last behind two Wizards: the first one always wins.
    both_wizards = make_view(
        None, others={"B": [Wizard()], "C": [Wizard()]}, order=("B", "C", "A")
    )
    assert blind_win_chance(both_wizards, unseen_cards([Wizard(), Wizard()])) == 0.0
    # Playing first against two Jesters: whatever our card is, it wins.
    both_jesters = make_view(
        None, others={"B": [Jester()], "C": [Jester()]}, order=("A", "B", "C")
    )
    assert blind_win_chance(both_jesters, unseen_cards([Jester(), Jester()])) == 1.0


# --- the heuristic bot ---------------------------------------------------------


def test_it_calls_what_the_hand_is_worth() -> None:
    bot = HeuristicAgent()
    trump = card(GREEN, 5)
    wizards = make_view([Wizard(), Wizard(), Wizard()], trump=trump)
    jesters = make_view([Jester(), Jester(), Jester()], trump=trump)
    assert asyncio.run(bot.ask_call(wizards, None)) == 3
    assert asyncio.run(bot.ask_call(jesters, None)) == 0


def test_it_never_calls_the_forbidden_number() -> None:
    bot = HeuristicAgent()
    view = make_view([Wizard(), Wizard(), Wizard()], trump=card(GREEN, 5))
    assert asyncio.run(bot.ask_call(view, 3)) == 2


def test_it_calls_the_fair_share_when_it_sees_nothing() -> None:
    view = make_view(None, round_number=6, trump=card(GREEN, 5))
    assert asyncio.run(HeuristicAgent().ask_call(view, None)) == 2  # 6 / 3 players


def test_wanting_a_trick_and_playing_last_it_wins_with_the_cheapest_winner() -> None:
    hand = [card(RED, 12), card(RED, 10), card(RED, 2)]
    table = [("B", card(RED, 5)), ("C", card(RED, 9))]
    view = make_view(hand, table, call=1, tricks_won=0)
    assert asyncio.run(HeuristicAgent().ask_card(view, hand)) == card(RED, 10)


def test_not_wanting_a_trick_it_dumps_its_strongest_sure_loser() -> None:
    hand = [card(RED, 12), card(RED, 3)]
    table = [("B", Wizard()), ("C", card(RED, 5))]
    view = make_view(hand, table, call=0, tricks_won=0)
    assert asyncio.run(HeuristicAgent().ask_card(view, hand)) == card(RED, 12)


def test_not_wanting_a_trick_it_keeps_the_wizard_when_it_could_win() -> None:
    hand = [Wizard(), card(RED, 3)]
    view = make_view(hand, [], call=0, tricks_won=0, order=("A", "B", "C"))
    assert asyncio.run(HeuristicAgent().ask_card(view, hand)) == card(RED, 3)


def test_it_passes_the_best_cards_when_the_hand_is_too_strong_for_its_call() -> None:
    hand = [Wizard(), Wizard(), card(RED, 3), Jester(), card(BLUE, 4)]
    rule = PassRule(2, Direction.RIGHT)
    strong = make_view(hand, call=0, trump=card(GREEN, 5))
    passed = asyncio.run(HeuristicAgent().ask_card_to_pass(strong, rule, "C"))
    assert sorted(passed, key=str) == [Wizard(), Wizard()]


def test_it_passes_the_worst_cards_when_it_needs_more_strength() -> None:
    hand = [Wizard(), card(RED, 13), card(RED, 3), Jester(), card(BLUE, 4)]
    rule = PassRule(2, Direction.LEFT)
    weak = make_view(hand, call=5, trump=card(GREEN, 5))
    passed = asyncio.run(HeuristicAgent().ask_card_to_pass(weak, rule, "C"))
    assert sorted(passed, key=str) == sorted([Jester(), card(RED, 3)], key=str)


def test_it_does_not_pass_away_the_cards_that_make_its_call() -> None:
    # A real game: it called 3 with this hand and used to pass the Wizard and
    # the 13 of trump (the two cards that made the call) to its neighbour.
    hand = [
        Wizard(),
        card(BLUE, 13),
        card(BLUE, 12),
        Jester(),
        card(GREEN, 1),
        card(YELLOW, 3),
        card(YELLOW, 4),
        card(YELLOW, 9),
    ]
    rule = PassRule(2, Direction.RIGHT)
    view = make_view(hand, call=3, trump=card(BLUE, 6))
    passed = asyncio.run(HeuristicAgent().ask_card_to_pass(view, rule, "C"))
    assert Wizard() not in passed
    assert card(BLUE, 13) not in passed


def test_it_picks_its_strongest_suit_as_trump() -> None:
    hand = [card(RED, 2), card(BLUE, 13), card(BLUE, 9), card(GREEN, 1)]
    view = make_view(hand)
    assert asyncio.run(HeuristicAgent().ask_trump_color(view)) is BLUE


class RuleChecker:
    """Wraps a bot and fails the test if it ever gives an answer the rules reject."""

    def __init__(self, inner: PlayerAgent) -> None:
        self.inner = inner
        self.answers = 0

    async def on_event(self, event: GameEvent) -> None:
        on_event = getattr(self.inner, "on_event", None)
        if on_event is not None:
            await on_event(event)

    async def ask_trump_color(self, view: PlayerView) -> Color:
        self.answers += 1
        return await self.inner.ask_trump_color(view)

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        self.answers += 1
        call = await self.inner.ask_call(view, forbidden_call)
        assert 0 <= call <= view.round_number
        assert call != forbidden_call
        return call

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        self.answers += 1
        cards = await self.inner.ask_card_to_pass(view, rule, recipient)
        hand = list(view.own_hand or [])
        assert len(cards) == rule.count
        for passed in cards:
            assert passed in hand
            hand.remove(passed)
        return cards

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        self.answers += 1
        played = await self.inner.ask_card(view, legal_cards)
        assert played in legal_cards
        return played


def test_the_bots_never_give_an_answer_the_rules_reject() -> None:
    for seed in range(5):
        checked = {
            name: RuleChecker(
                HeuristicAgent() if i < 2 else RandomAgent(seed * 10 + i)
            )
            for i, name in enumerate(NAMES)
        }
        run_game(seed, agents=checked)
        assert all(c.answers > 100 for c in checked.values())


def test_the_bot_counts_the_cards_played_through_the_events() -> None:
    bot = HeuristicAgent()
    view = make_view([card(RED, 5), card(RED, 6)], trump=card(GREEN, 5))
    before = bot.unseen_for(view)
    assert len(before) == 60 - 3  # minus our hand and the trump card

    seven = card(BLUE, 7)
    asyncio.run(bot.on_event(CardPlayed("B", seven)))
    after = bot.unseen_for(view)
    assert len(after) == len(before) - 1 and seven not in after

    # A card that is on the table is also an event: it must not be counted twice.
    on_table = make_view(view.own_hand, [("B", seven)], trump=card(GREEN, 5))
    assert bot.unseen_for(on_table) == after

    asyncio.run(bot.on_event(RoundStarted(2, "C", Trump(None, None))))  # a new round
    assert len(bot.unseen_for(view)) == len(before)


# --- tournament ------------------------------------------------------------------


def test_the_heuristic_bot_clearly_beats_random_play() -> None:
    standings = {s.kind: s for s in run_tournament(["heuristic", "random", "random"], 30)}
    assert standings["heuristic"].mean > standings["random"].mean + 40
    assert standings["heuristic"].wins >= 27


def test_a_tournament_replays_identically() -> None:
    first = run_tournament(["heuristic", "random", "random"], 6, seed=5)
    second = run_tournament(["heuristic", "random", "random"], 6, seed=5)
    assert [(s.kind, s.points, s.wins) for s in first] == [
        (s.kind, s.points, s.wins) for s in second
    ]


def test_every_seat_gets_played_the_same_number_of_times() -> None:
    standings = run_tournament(["heuristic", "random", "random"], 6)
    by_kind = {s.kind: len(s.points) for s in standings}
    assert by_kind == {"heuristic": 6, "random": 12}
    assert "heuristic" in format_standings(standings, 6)


def test_the_seats_rotate_so_everybody_sits_everywhere() -> None:
    kinds = ["heuristic", "random", "random"]
    seatings = [seating_for(kinds, game) for game in range(3)]
    assert seatings[0] == kinds
    assert seatings[1] == ["random", "random", "heuristic"]
    assert sorted(s.index("heuristic") for s in seatings) == [0, 1, 2]
