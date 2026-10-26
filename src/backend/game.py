from src.backend.cards import Deck, Card
from src.backend.player import Player


class Game:

    def __init__(self, players: list[Player], deck: Deck) -> None:
        print("Starting game...")
        self.players = players
        self.deck = deck

    def deal_cards(self, n_cards: int) -> None:
        """Deals n_cards to each player."""
        for _ in range(1, n_cards + 1):
            for player in self.players:
                card = self.deck.draw()
                player.add_card_to_hand(card)

    def deal_trump_card(self):
        self.trump_card: Card = self.deck.draw()

    def check_legal_play(self, player: Player, card: Card) -> bool:
        """Checks if the card played by the player is legal."""
        if card.color is None:
            return True
        if card.color == self.trump_card.color:
            return True
        for c in player.cards:
            if c.color == self.trump_card.color:
                return False
        return True
                