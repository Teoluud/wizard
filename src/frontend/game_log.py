from src.backend.cards import Card, Jester, Wizard
from src.backend.events import (
    CallMade,
    CardPlayed,
    CardsPassed,
    GameEvent,
    GameOver,
    GameStarted,
    RoundScored,
    RoundStarted,
    TrickWon,
    TrumpChosen,
)
from src.backend.view import PlayerStatus, Trump


def describe_card(card: Card) -> str:
    if isinstance(card, Wizard):
        return "Wizard"
    if isinstance(card, Jester):
        return "Jester"
    return f"{card.number} {card.color}"


def describe_trump(trump: Trump) -> str:
    if trump.card is None:
        return "none"
    if isinstance(trump.card, Jester):
        return "Jester (no trump)"
    if isinstance(trump.card, Wizard):
        return "Wizard (the dealer picks the suit)"
    return describe_card(trump.card)


def describe_scores(scores: list[PlayerStatus]) -> str:
    return ", ".join(
        f"{s.name} {s.points} (called {s.call}, won {s.tricks_won})" for s in scores
    )


class GameLog:
    """An observer that prints the game as a play-by-play."""

    async def on_event(self, event: GameEvent) -> None:
        match event:
            case GameStarted(players=players, n_rounds=n_rounds):
                print(f"Game of {n_rounds} rounds: {', '.join(players)}")
            case RoundStarted(round_number=number, dealer=dealer, trump=trump):
                print(
                    f"\n=== Round {number}, dealer {dealer}, trump {describe_trump(trump)}"
                )
            case TrumpChosen(dealer=dealer, color=color):
                print(f"  {dealer} chooses {color} as trump")
            case CallMade(player=player, call=call):
                print(f"  {player} calls {call}")
            case CardsPassed(count=count, direction=direction):
                print(f"  everybody passes {count} cards to the {direction.value}")
            case CardPlayed(player=player, card=card):
                print(f"    {player} plays {describe_card(card)}")
            case TrickWon(winner=winner):
                print(f"  -> {winner} wins the trick")
            case RoundScored(scores=scores):
                print(f"  points: {describe_scores(scores)}")
            case GameOver(scores=scores):
                ranking = sorted(scores, key=lambda s: s.points, reverse=True)
                print("\nFinal: " + ", ".join(f"{s.name} {s.points}" for s in ranking))
