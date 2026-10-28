from src.backend.cards import Card


class Player:

    def __init__(self, name: str) -> None:
        self.name = name
        self.cards: list[Card] = []
        self._points: int = 0
        self._tricks_won: int = 0
        self._call: int | None = None

    def add_card_to_hand(self, card: Card) -> None:
        self.cards.append(card)

    def call_tricks(self, tricks: int) -> None:
        if tricks >= 0:
            self._call = tricks
        else:
            raise ValueError(f"Tricks called ({tricks}) must be greater than 0.")

    def play_card(self, card: Card) -> Card:
        self.cards.remove(card)
        return card

    def remove_card_from_hand(self, card: Card) -> None:
        self.cards.remove(card)

    def win_trick(self) -> None:
        self._tricks_won += 1

    def update_points(self) -> None:
        """Updates the current points based on the win/loss.
        - WIN: hands called + 2
        - LOSE: - |hands called - hands won|
        """
        if self._call is None:
            raise ValueError("Can't update points if there was no call.")

        if self._tricks_won == self._call:
            self._points += self._call + 2
        else:
            self._points -= abs(self._call - self._tricks_won)

    @property
    def call(self) -> int | None:
        return self._call

    @property
    def tricks_won(self) -> int:
        return self._tricks_won

    @property
    def points(self) -> int:
        return self._points

    def reset_for_round(self) -> None:
        self.cards = []
        self._tricks_won = 0
        self._call = None

    def __str__(self) -> str:
        return self.name + ": " + str(self._points)
