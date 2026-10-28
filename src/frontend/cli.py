from src.backend.cards import Card, Color, Jester, Wizard
from src.backend.player import Player
from src.backend.rules import PassRule
from src.backend.view import PlayerView, Trump

# Home + clear screen + clear scrollback, so earlier hands can't be scrolled to.
_CLEAR_SCREEN = "\033[H\033[2J\033[3J"


class CliInterface:
    """Terminal implementation of GameInterface (one shared screen)."""

    def ask_trump_color(self, view: PlayerView) -> Color:
        self._hand_over_to(view.player)
        print(f"=== Round {view.round_number} ===")
        print("The trump card is a Wizard: as the dealer, you choose the trump suit.\n")
        self._print_hands(view)
        colors = list(Color)
        print("Suits:")
        for i, color in enumerate(colors, start=1):
            print(f"  {i}) {color}")
        choice = self._ask_index("Choose the trump suit: ", len(colors))
        return colors[choice - 1]

    def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        self._hand_over_to(view.player)
        print(f"\n=== Round {view.round_number} ===")
        print(f"Trump: {self._format_trump(view.trump)}")
        self._print_hands(view)
        if forbidden_call is not None:
            print(f"\nYou are the dealer: you can't call {forbidden_call}.")

        while True:
            raw = input(f"{view.player.name}, how many tricks do you call? ")
            try:
                call = int(raw)
            except ValueError:
                print("Please enter a whole number.")
                continue
            if not 0 <= call <= view.round_number:
                print(f"The call must be between 0 and {view.round_number}.")
            elif call == forbidden_call:
                print(f"As the dealer, you can't call {forbidden_call}.")
            else:
                return call

    def ask_card_to_pass(self, view: PlayerView, rule: PassRule, recipient: Player) -> list[Card]:
        self._hand_over_to(view.player)
        print(f"=== Round {view.round_number} ===")
        print(f"Your call: {view.player.call}")
        print(f"Trump: {self._format_trump(view.trump)}\n")
        print(
            f"Pass {rule.count} cards to {recipient.name} "
            f"(the player on your {rule.direction.value}).\n"
        )
        remaining = list(self._own_hand(view))
        passed: list[Card] = []
        for n in range(1, rule.count + 1):
            print("Your hand:")
            for i, card in enumerate(remaining, start=1):
                print(f"  {i}) {self._format_card(card)}")
            choice = self._ask_index(
                f"Card {n} of {rule.count} to pass: ", len(remaining)
            )
            passed.append(remaining.pop(choice - 1))
            print()
        return passed

    def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        player = view.player
        self._hand_over_to(player)
        print(f"Your tricks: {player.tricks_won}/{player.call}\n")
        print(f"Trump: {self._format_trump(view.trump)}")
        print(f"On the table: {self._format_table(view.table)}\n")
        self._print_hands(view)

        if not view.can_see_own_hand:
            # Full blind rounds deal a single card, so there is nothing to choose.
            input("Press Enter to play your hidden card...")
            return legal_cards[0]

        print("Playable:")
        for i, card in enumerate(legal_cards, start=1):
            print(f"  {i}) {self._format_card(card)}")
        choice = self._ask_index("Choose a card: ", len(legal_cards))
        return legal_cards[choice - 1]

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

    @staticmethod
    def _ask_index(prompt: str, size: int) -> int:
        """Asks until the player enters a number between 1 and `size`."""
        while True:
            raw = input(prompt)
            try:
                choice = int(raw)
            except ValueError:
                print("Please enter a number.")
                continue
            if 1 <= choice <= size:
                return choice
            print(f"Choose a number between 1 and {size}.")

    @staticmethod
    def _own_hand(view: PlayerView) -> list[Card]:
        for owner, cards in view.hands:
            if owner is view.player:
                return cards
        raise ValueError(f"{view.player.name} can't see their own hand.")

    def _print_hands(self, view: PlayerView) -> None:
        """Prints the hands the player may see (their own, or the others')."""
        for owner, cards in view.hands:
            label = "Your hand" if owner is view.player else f"{owner.name}'s hand"
            print(f"{label}: {self._format_hand(cards)}")
        if not view.can_see_own_hand:
            print("You can't see your own cards right now.")

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

    def _format_trump(self, trump: Trump) -> str:
        card = trump.card
        if card is None:
            return "none (last round)"
        if isinstance(card, Jester):
            return "Jester (no trump this round)"
        if isinstance(card, Wizard):
            if trump.color is None:
                return "Wizard (suit not chosen yet)"
            return f"Wizard (the dealer chose {trump.color})"
        return self._format_card(card)

    def _format_hand(self, cards: list[Card]) -> str:
        return ", ".join(self._format_card(c) for c in cards)

    def _format_table(self, table: list[tuple[Player, Card]]) -> str:
        if not table:
            return "(empty, you lead)"
        return ", ".join(f"{p.name}: {self._format_card(c)}" for p, c in table)
