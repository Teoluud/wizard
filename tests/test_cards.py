from src.backend.cards import Card, Deck, Jester, Wizard


def test_deck_has_the_60_cards_of_wizard() -> None:
    cards = Deck(0).cards
    assert len(cards) == 60
    assert sum(isinstance(c, Wizard) for c in cards) == 4
    assert sum(isinstance(c, Jester) for c in cards) == 4


def test_same_seed_gives_the_same_deck() -> None:
    assert Deck(7).cards == Deck(7).cards
    assert Deck(7).cards != Deck(8).cards


def test_reset_deck_keeps_the_seeded_sequence_reproducible() -> None:
    first, second = Deck(3), Deck(3)
    first.draw()
    first.reset_deck()
    second.draw()
    second.reset_deck()
    assert first.cards == second.cards


def test_cards_survive_a_dict_round_trip() -> None:
    cards = Deck(0).cards
    assert [Card.from_dict(c.to_dict()) for c in cards] == cards
