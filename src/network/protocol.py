import asyncio
import contextlib
import json
from typing import Any, Mapping, cast

from src.backend.cards import Card, Color
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
from src.backend.rules import Direction, PassRule
from src.backend.view import PlayerStatus, PlayerView, Trump


class JsonCodec:
    """Serializes and deserializes views, rules, and events to/from JSON-ready dicts."""

    @staticmethod
    def encode_trump(trump: Trump) -> dict[str, Any]:
        return {
            "card": trump.card.to_dict() if trump.card is not None else None,
            "color": trump.color.value if trump.color is not None else None,
        }

    @staticmethod
    def decode_trump(data: Mapping[str, Any]) -> Trump:
        raw_card = data.get("card")
        raw_color = data.get("color")
        return Trump(
            card=Card.from_dict(raw_card) if raw_card is not None else None,
            color=Color(raw_color) if raw_color is not None else None,
        )

    @staticmethod
    def encode_status(status: PlayerStatus) -> dict[str, Any]:
        return {
            "name": status.name,
            "call": status.call,
            "tricks_won": status.tricks_won,
            "points": status.points,
            "card_count": status.card_count,
        }

    @staticmethod
    def decode_status(data: Mapping[str, Any]) -> PlayerStatus:
        return PlayerStatus(
            name=str(data["name"]),
            call=int(data["call"]) if data.get("call") is not None else None,
            tricks_won=int(data["tricks_won"]),
            points=int(data["points"]),
            card_count=int(data["card_count"]),
        )

    @classmethod
    def encode_view(cls, view: PlayerView) -> dict[str, Any]:
        return {
            "player_name": view.player_name,
            "round_number": view.round_number,
            "dealer_name": view.dealer_name,
            "trump": cls.encode_trump(view.trump),
            "players": [cls.encode_status(p) for p in view.players],
            "hands": [
                [owner, [c.to_dict() for c in cards]] for owner, cards in view.hands
            ],
            "table": [[player, card.to_dict()] for player, card in view.table],
        }

    @classmethod
    def decode_view(cls, data: Mapping[str, Any]) -> PlayerView:
        return PlayerView(
            player_name=str(data["player_name"]),
            round_number=int(data["round_number"]),
            dealer_name=str(data["dealer_name"]),
            trump=cls.decode_trump(data["trump"]),
            players=[cls.decode_status(p) for p in data["players"]],
            hands=[
                (str(owner), [Card.from_dict(c) for c in cards])
                for owner, cards in data["hands"]
            ],
            table=[
                (str(player), Card.from_dict(card)) for player, card in data["table"]
            ],
        )

    @staticmethod
    def encode_pass_rule(rule: PassRule) -> dict[str, Any]:
        return {"count": rule.count, "direction": rule.direction.value}

    @staticmethod
    def decode_pass_rule(data: Mapping[str, Any]) -> PassRule:
        return PassRule(
            count=int(data["count"]), direction=Direction(data["direction"])
        )

    @classmethod
    def encode_event(cls, event: GameEvent) -> dict[str, Any]:
        match event:
            case GameStarted(players=players, n_rounds=n_rounds):
                return {
                    "event": "game_started",
                    "players": players,
                    "n_rounds": n_rounds,
                }
            case RoundStarted(round_number=num, dealer=dealer, trump=trump):
                return {
                    "event": "round_started",
                    "round_number": num,
                    "dealer": dealer,
                    "trump": cls.encode_trump(trump),
                }
            case TrumpChosen(dealer=dealer, color=color):
                return {
                    "event": "trump_chosen",
                    "dealer": dealer,
                    "color": color.value,
                }
            case CallMade(player=player, call=call):
                return {
                    "event": "call_made",
                    "player": player,
                    "call": call,
                }
            case CardsPassed(count=count, direction=direction):
                return {
                    "event": "cards_passed",
                    "count": count,
                    "direction": direction.value,
                }
            case CardPlayed(player=player, card=card):
                return {
                    "event": "card_played",
                    "player": player,
                    "card": card.to_dict(),
                }
            case TrickWon(winner=winner, table=table):
                return {
                    "event": "trick_won",
                    "winner": winner,
                    "table": [[p, c.to_dict()] for p, c in table],
                }
            case RoundScored(round_number=num, scores=scores):
                return {
                    "event": "round_scored",
                    "round_number": num,
                    "scores": [cls.encode_status(s) for s in scores],
                }
            case GameOver(scores=scores):
                return {
                    "event": "game_over",
                    "scores": [cls.encode_status(s) for s in scores],
                }

    @classmethod
    def decode_event(cls, data: Mapping[str, Any]) -> GameEvent:
        kind = data["event"]
        match kind:
            case "game_started":
                return GameStarted(
                    players=list(data["players"]), n_rounds=int(data["n_rounds"])
                )
            case "round_started":
                return RoundStarted(
                    round_number=int(data["round_number"]),
                    dealer=str(data["dealer"]),
                    trump=cls.decode_trump(data["trump"]),
                )
            case "trump_chosen":
                return TrumpChosen(
                    dealer=str(data["dealer"]),
                    color=Color(data["color"]),
                )
            case "call_made":
                return CallMade(
                    player=str(data["player"]),
                    call=int(data["call"]),
                )
            case "cards_passed":
                return CardsPassed(
                    count=int(data["count"]),
                    direction=Direction(data["direction"]),
                )
            case "card_played":
                return CardPlayed(
                    player=str(data["player"]),
                    card=Card.from_dict(data["card"]),
                )
            case "trick_won":
                return TrickWon(
                    winner=str(data["winner"]),
                    table=[(str(p), Card.from_dict(c)) for p, c in data["table"]],
                )
            case "round_scored":
                return RoundScored(
                    round_number=int(data["round_number"]),
                    scores=[cls.decode_status(s) for s in data["scores"]],
                )
            case "game_over":
                return GameOver(
                    scores=[cls.decode_status(s) for s in data["scores"]],
                )
            case _:
                raise ValueError(f"Unknown event type: {kind}")


class JsonStream:
    """Wraps an asyncio StreamReader/StreamWriter pair to send/receive JSON lines."""

    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer

    async def send(self, payload: Mapping[str, Any]) -> None:
        line = json.dumps(payload) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    async def receive(self) -> dict[str, Any]:
        line = await self._reader.readline()
        if not line:
            raise ConnectionResetError("Peer closed the connection.")
        packet = json.loads(line.decode("utf-8"))
        if not isinstance(packet, dict):
            raise ValueError(f"Expected a JSON object, got: {packet!r}")
        return cast(dict[str, Any], packet)

    async def close(self) -> None:
        """Closes the connection; a peer that is already gone is not an error."""
        self._writer.close()
        with contextlib.suppress(OSError):
            await self._writer.wait_closed()
