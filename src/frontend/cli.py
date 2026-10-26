from src.backend.cards import Card, Jester, Wizard
from src.backend.player import Player

# Home + clear screen + clear scrollback, so earlier hands can't be scrolled to.
_CLEAR_SCREEN = "\033[H\033[2J\033[3J"


class CliInterface:
    """Terminal implementation of GameInterface (one shared screen)."""

    def ask_call(self, player: Player, round_number: int, trump: Card | None) -> int:
        self._hand_over_to(player)
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

    def ask_card(
        self,
        player: Player,
        legal_cards: list[Card],
        trump: Card | None,
        table: list[tuple[Player, Card]],
    ) -> Card:
        self._hand_over_to(player)
        print(f"Your tricks: {player.tricks_won}/{player.call}\n")
        print(f"Trump: {self._format_trump(trump)}")
        print(f"On the table: {self._format_table(table)}\n")
        print(f"Your hand: {self._format_hand(player.cards)}")
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

    def show_trick_winner(
        self, winner: Player, table: list[tuple[Player, Card]]
    ) -> None:
        self._clear()
        print(f"Trick: {self._format_table(table)}")
        print(f"-> {winner.name} wins the trick.")
        input("\nPress Enter to continue...")

    def show_scores(self, players: list[Player]) -> None:
        print("\nScores:")
        for player in sorted(players, key=lambda p: p.points, reverse=True):
            print(f"  {player}")
        input("\nPress Enter to continue...")

    def _hand_over_to(self, player: Player) -> None:
        """Hides the previous screen and waits for `player` to take over."""
        self._clear()
        input(f"Pass the keyboard to {player.name}, then press Enter...")
        self._clear()
        print(f"--- {player.name} ---")

    @staticmethod
    def _clear() -> None:
        print(_CLEAR_SCREEN, end="", flush=True)

    @staticmethod
    def _format_card(card: Card) -> str:
        if isinstance(card, Wizard):
            return "Wizard"
        if isinstance(card, Jester):
            return "Jester"
        return f"{card.number} {card.color}"

    def _format_trump(self, trump: Card | None) -> str:
        return self._format_card(trump) if trump else "none"

    def _format_hand(self, cards: list[Card]) -> str:
        return ", ".join(self._format_card(c) for c in cards)

    def _format_table(self, table: list[tuple[Player, Card]]) -> str:
        if not table:
            return "(empty, you lead)"
        return ", ".join(f"{p.name}: {self._format_card(c)}" for p, c in table)
