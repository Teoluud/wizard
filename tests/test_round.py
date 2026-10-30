from collections import Counter

import pytest

from src.backend.cards import Card, Color, Deck, Jester, Wizard
from tests.helpers import call_all, find_round, make_round


def test_only_the_dealer_is_restricted_and_the_calls_cannot_add_up() -> None:
    round_, players = make_round(3)
    assert round_.dealer is players[-1]
    round_.set_call(players[0], 1)
    round_.set_call(players[1], 1)
    assert round_.forbidden_call(players[0]) is None
    assert round_.forbidden_call(players[2]) == 1  # 1 + 1 + 1 would be 3 tricks
    with pytest.raises(ValueError):
        round_.set_call(players[2], 1)
    round_.set_call(players[2], 0)


def test_the_dealer_is_free_when_the_others_already_called_too_much() -> None:
    round_, players = make_round(2)
    round_.set_call(players[0], 2)
    round_.set_call(players[1], 2)
    assert round_.forbidden_call(players[2]) is None
    round_.set_call(players[2], 0)


def test_a_wizard_trump_blocks_the_game_until_the_dealer_picks_a_suit() -> None:
    round_, players = find_round(
        3, lambda c: isinstance(c, Wizard), choose_trump=False
    )
    assert round_.needs_trump_choice
    assert round_.trump_color is None
    assert round_.trick is None
    with pytest.raises(ValueError):
        round_.set_call(players[0], 0)

    round_.choose_trump_color(Color.GREEN)
    assert round_.trump_color is Color.GREEN
    assert round_.trick is not None
    round_.set_call(players[0], 0)
    with pytest.raises(ValueError):
        round_.choose_trump_color(Color.RED)


def test_a_jester_trump_means_no_trump() -> None:
    round_, _ = find_round(3, lambda c: isinstance(c, Jester))
    assert not round_.needs_trump_choice
    assert round_.trump_color is None
    assert round_.trick is not None


def test_the_last_round_has_no_trump_card() -> None:
    round_, _ = make_round(20)  # 3 players x 20 cards: the whole deck is dealt
    assert round_.trump_card is None
    assert round_.trump_color is None


@pytest.mark.parametrize("number, offset", [(8, -1), (9, 1)])
def test_cards_go_to_the_right_in_round_8_and_to_the_left_in_round_9(
    number: int, offset: int
) -> None:
    round_, players = make_round(number)
    for i, player in enumerate(players):
        assert round_.pass_target(player) is players[(i + offset) % 3]


@pytest.mark.parametrize("number, offset", [(8, -1), (9, 1)])
def test_passing_swaps_the_chosen_cards_and_nothing_else(
    number: int, offset: int
) -> None:
    round_, players = make_round(number)
    call_all(round_)
    assert round_.pending_pass is not None
    before = [Counter(p.cards) for p in players]
    passes = {p: p.cards[:2] for p in players}

    round_.pass_cards(passes)

    for i, player in enumerate(players):
        giver = players[(i - offset) % 3]  # the one who passes to `player`
        expected = before[i] - Counter(passes[player]) + Counter(passes[giver])
        assert Counter(player.cards) == expected
        assert len(player.cards) == number
    assert round_.pending_pass is None


def test_a_bad_pass_changes_nothing() -> None:
    round_, players = make_round(8)
    call_all(round_)
    before = [list(p.cards) for p in players]
    good = {p: p.cards[:2] for p in players}
    foreign = next(c for c in Deck().cards if c not in players[0].cards)

    with pytest.raises(ValueError):  # too few cards
        round_.pass_cards({**good, players[0]: players[0].cards[:1]})
    with pytest.raises(ValueError):  # a card the player doesn't have
        round_.pass_cards({**good, players[0]: [foreign, players[0].cards[0]]})
    with pytest.raises(ValueError):  # somebody didn't choose
        round_.pass_cards({p: good[p] for p in players[1:]})

    assert [list(p.cards) for p in players] == before
    assert round_.pending_pass is not None


def test_cards_cannot_be_played_before_the_passing() -> None:
    round_, _ = make_round(8)
    call_all(round_)
    player = round_.current_player
    with pytest.raises(ValueError):
        round_.play_card(player, player.cards[0])


def test_a_card_that_is_not_in_the_hand_cannot_be_played() -> None:
    round_, _ = make_round(3)
    call_all(round_)
    player = round_.current_player
    foreign = next(
        c
        for c in Deck().cards
        if c not in player.cards and not isinstance(c, (Wizard, Jester))
    )
    with pytest.raises(ValueError):
        round_.play_card(player, foreign)
    assert len(player.cards) == 3


def test_round_1_shows_everybody_else_but_never_your_own_cards() -> None:
    round_, players = make_round(1)
    call_all(round_)  # also holds once the tricks start
    for player in players:
        view = round_.view_for(player)
        assert view.own_hand is None
        assert not view.can_see_own_hand
        others = sorted(p.name for p in players if p is not player)
        assert sorted(owner for owner, _ in view.hands) == others


def test_round_6_is_called_blind_and_then_everybody_sees_their_cards() -> None:
    round_, players = make_round(6)
    for player in players:
        assert round_.view_for(player).hands == []
    call_all(round_)
    for player in players:
        view = round_.view_for(player)
        assert view.hands == [(player.name, list(player.cards))]


def test_a_normal_round_shows_only_your_own_cards() -> None:
    round_, players = make_round(3)
    for player in players:
        view = round_.view_for(player)
        assert view.hands == [(player.name, list(player.cards))]
        assert view.own_hand == list(player.cards)


def test_views_are_plain_data_and_show_the_public_state() -> None:
    round_, players = make_round(3)
    round_.set_call(players[0], 2)
    view = round_.view_for(players[1])
    assert view.player_name == "B"
    assert view.dealer_name == "C"
    assert [s.name for s in view.players] == ["A", "B", "C"]
    assert view.players[0].call == 2
    assert view.status.name == "B" and view.status.card_count == 3
    assert view.table == []
    assert all(isinstance(owner, str) for owner, _ in view.hands)
    assert [Card.from_dict(c.to_dict()) for c in view.hands[0][1]] == view.hands[0][1]
