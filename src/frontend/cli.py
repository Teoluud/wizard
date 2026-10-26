from src.backend.cards import Card, Jester, Wizard
from src.backend.player import Player


class CliInterface:
    """Terminal implementation of GameInterface."""

    def ask_call(self, player: Player, round_number: int, trump: Card | None) -> int:
        print(f"\n=== Round {round_number} ===")
        print(f"Trump: {self._format_card(trump) if trump else 'none'}")
        print(f"{player.name}, your hand: {self._format_hand(player.cards)}")

        while True:
            raw = input(f"{player.name}, how many tricks do you call? ")
            try:
                call = int(raw)
            except ValueError:
                print("Please enter a whole number.")
                continue
            if 0 <= call <= round_number:
                return call
            print(f"The call must be between 0 and {round_number}.")

    def ask_card(self, player: Player, legal_cards: list[Card]) -> Card:
        print(f"\n{player.name}'s turn.")
        print(f"Your hand:   {self._format_hand(player.cards)}")
        print("Playable:")
        for i, card in enumerate(legal_cards, start=1):
            print(f"  {i}) {self._format_card(card)}")

        while True:
            raw = input("Choose a card: ")
            try:
                choice = int(raw)
            except ValueError:
                print("Please enter the number of a card.")
                continue
            if 1 <= choice <= len(legal_cards):
                return legal_cards[choice - 1]
            print(f"Choose a number between 1 and {len(legal_cards)}.")

    def show_trick_winner(self, winner: Player) -> None:
        print(f"-> {winner.name} wins the trick.")

    def show_scores(self, players: list[Player]) -> None:
        print("\nScores:")
        for player in sorted(players, key=lambda p: p.points, reverse=True):
            print(f"  {player}")

    @staticmethod
    def _format_card(card: Card) -> str:
        if isinstance(card, Wizard):
            return "Wizard"
        if isinstance(card, Jester):
            return "Jester"
        return f"{card.number} {card.color}"

    def _format_hand(self, cards: list[Card]) -> str:
        return ", ".join(self._format_card(c) for c in cards)