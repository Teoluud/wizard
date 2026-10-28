from src.backend.cards import Card, Color, Jester, Wizard
from src.backend.player import Player


class Trick:
    """The cards played by every player in a single trick."""

    def __init__(self, players: list[Player], trump_color: Color | None) -> None:
        self.players = players
        self.trump_color = trump_color
        self.plays: list[tuple[Player, Card]] = []

    @property
    def is_complete(self) -> bool:
        """Checks if the trick is over (everyone has played)."""
        return len(self.plays) == len(self.players)

    @property
    def current_player(self) -> Player:
        return self.players[len(self.plays)]

    @property
    def led_color(self) -> Color | None:
        """Suit to follow, or None if only Wizards or Jesters came first."""
        for _, card in self.plays:
            if not isinstance(card, Wizard) and not isinstance(card, Jester):
                return card.color
        return None

    def is_legal(self, player: Player, card: Card) -> bool:
        led = self.led_color
        if card.color is None or led is None or card.color == led:
            return True
        return all(c.color != led for c in player.cards)

    def legal_cards(self, player: Player) -> list[Card]:
        return [c for c in player.cards if self.is_legal(player, c)]

    def add_play(self, player: Player, card: Card) -> None:
        self.plays.append((player, card))

    def winner(self) -> Player:
        if not self.is_complete:
            raise ValueError("Trick is not complete.")
        for player, card in self.plays:
            # first Wizard wins
            if isinstance(card, Wizard):
                return player
        candidates = [(p, c) for p, c in self.plays if not isinstance(c, Jester)]
        if not candidates:  # all Jesters: first one wins
            return self.plays[0][0]
        trumps = [(p, c) for p, c in candidates if c.color == self.trump_color]
        # build the pool: only trump cards if present, otherwise only cards with the led color
        pool = trumps or [(p, c) for p, c in candidates if c.color == self.led_color]
        return max(pool, key=lambda play: play[1].number)[0]
