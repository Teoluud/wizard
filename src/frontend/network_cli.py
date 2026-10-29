
from src.ai.game_log import describe_card, describe_trump
from src.backend.events import (
    CallMade,
    CardsPassed,
    CardPlayed,
    GameEvent,
    GameOver,
    GameStarted,
    RoundScored,
    RoundStarted,
    TrickWon,
    TrumpChosen
)
from src.backend.view import PlayerStatus
from src.frontend.cli import CliInterface


class NetworkCliAgent(CliInterface):
    """Single-seat terminal UI for a networked client.
    
    Reuses all input prompts from `CliInterface`, removes the hot-seat
    keyboard handover prompt, and prints live public events as they arrive.
    """

    def _hand_over_to(self, player_name: str) -> None:
        print(f"\n--- Your turn, {player_name} ---")

    def _show_scores(self, scores: list[PlayerStatus], final: bool = False) -> None:
        print("\nFinal scores:" if final else "\nScores:")
        for score in sorted(scores, key=lambda s: s.points, reverse=True):
            print(
                f"  {score.name}: {score.points} "
                f"(called {score.call}, won {score.tricks_won})"
            )

    async def on_event(self, event: GameEvent) -> None:
        match event:
            case GameStarted(players=players, n_rounds=n_rounds):
                print(
                    f"\nGame started ({n_rounds} rounds): {', '.join(players)}"
                )
            case RoundStarted(round_number=number, dealer=dealer, trump=trump):
                print(
                    f"\n=== Round {number} | Dealer: {dealer} | "
                    f"Trump: {describe_trump(trump)} ==="
                )
            case TrumpChosen(dealer=dealer, color=color):
                print(f"  {dealer} chose {color} as the trump suit.")
            case CallMade(player=player, call=call):
                print(f"  {player} called {call}.")
            case CardsPassed(count=count, direction=direction):
                print(f"  Everyone passed {count} cards to the {direction.value}.")
            case CardPlayed(player=player, card=card):
                print(f"  {player} played {describe_card(card)}.")
            case TrickWon(winner=winner, table=table):
                print(f"Trick: {self._format_table(table)}")
                print(f"-> {winner} wins the trick.")
            case RoundScored(scores=scores):
                self._show_scores(scores)
            case GameOver(scores=scores):
                self._show_scores(scores, final=True)
