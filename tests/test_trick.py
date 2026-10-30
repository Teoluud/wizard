import pytest

from src.backend.cards import Card, Color, Jester, Wizard
from src.backend.player import Player
from src.backend.trick import Trick

RED, BLUE, GREEN = Color.RED, Color.BLUE, Color.GREEN


def card(color: Color, number: int) -> Card:
    return Card(color=color, number=number)


def make_trick(
    plays: list[Card], trump: Color | None = None
) -> tuple[Trick, list[Player]]:
    """A trick for players A, B, C where the first `len(plays)` cards were played."""
    players = [Player("A"), Player("B"), Player("C")]
    trick = Trick(players, trump)
    for player, played in zip(players, plays):
        trick.add_play(player, played)
    return trick, players


def test_a_leading_jester_does_not_set_the_suit() -> None:
    trick, _ = make_trick([Jester(), card(RED, 5)])
    assert trick.led_color is RED


def test_you_must_follow_the_led_suit_but_can_always_play_wizards_and_jesters() -> None:
    trick, players = make_trick([card(RED, 5)])
    hand = [card(RED, 3), card(BLUE, 9), Wizard(), Jester()]
    players[1].cards = list(hand)
    assert trick.legal_cards(players[1]) == [hand[0], hand[2], hand[3]]


def test_without_the_led_suit_anything_goes() -> None:
    trick, players = make_trick([card(RED, 5)])
    players[1].cards = [card(BLUE, 9), card(GREEN, 2)]
    assert trick.legal_cards(players[1]) == players[1].cards


def test_highest_card_of_the_led_suit_wins() -> None:
    trick, players = make_trick([card(RED, 5), card(RED, 9), card(BLUE, 12)])
    assert trick.winner() is players[1]


def test_trump_beats_the_led_suit() -> None:
    trick, players = make_trick(
        [card(RED, 12), card(GREEN, 2), card(RED, 9)], trump=GREEN
    )
    assert trick.winner() is players[1]


def test_highest_trump_wins() -> None:
    trick, players = make_trick(
        [card(GREEN, 2), card(GREEN, 9), card(RED, 13)], trump=GREEN
    )
    assert trick.winner() is players[1]


def test_the_first_wizard_wins() -> None:
    trick, players = make_trick([card(RED, 13), Wizard(), Wizard()], trump=RED)
    assert trick.winner() is players[1]


def test_a_trick_of_jesters_goes_to_the_first_one() -> None:
    trick, players = make_trick([Jester(), Jester(), Jester()])
    assert trick.winner() is players[0]


def test_jesters_never_win_over_a_number() -> None:
    trick, players = make_trick([Jester(), card(RED, 3), Jester()])
    assert trick.winner() is players[1]


def test_an_unfinished_trick_has_no_winner() -> None:
    trick, _ = make_trick([card(RED, 5)])
    with pytest.raises(ValueError):
        trick.winner()
