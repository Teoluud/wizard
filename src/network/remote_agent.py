from typing import Any

from src.backend.cards import Card, Color
from src.backend.events import GameEvent
from src.backend.rules import PassRule
from src.backend.view import PlayerView
from src.network.protocol import JsonCodec, JsonStream


class RemotePlayerAgent:
    """Server-side proxy for a remote client.

    Implements both `PlayerAgent` and `GameObserver` so `Game` automatically
    registers it for events and only ever sends it its own `PlayerView`.
    """

    def __init__(self, name: str, stream: JsonStream) -> None:
        self.name = name
        self._stream = stream

    async def ask_trump_color(self, view: PlayerView) -> Color:
        reply = await self._request("ask_trump_color", view=JsonCodec.encode_view(view))
        try:
            return Color(reply["color"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid trump color payload: {reply}") from exc

    async def ask_call(self, view: PlayerView, forbidden_call: int | None) -> int:
        reply = await self._request(
            "ask_call", view=JsonCodec.encode_view(view), forbidden_call=forbidden_call
        )
        try:
            return int(reply["call"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid call payload: {reply}") from exc

    async def ask_card_to_pass(
        self, view: PlayerView, rule: PassRule, recipient: str
    ) -> list[Card]:
        reply = await self._request(
            "ask_card_to_pass",
            view=JsonCodec.encode_view(view),
            rule=JsonCodec.encode_pass_rule(rule),
            recipient=recipient,
        )
        try:
            return [Card.from_dict(c) for c in reply["cards"]]
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid pass cards payload: {reply}") from exc

    async def ask_card(self, view: PlayerView, legal_cards: list[Card]) -> Card:
        reply = await self._request(
            "ask_card",
            view=JsonCodec.encode_view(view),
            legal_cards=[c.to_dict() for c in legal_cards],
        )
        try:
            return Card.from_dict(reply["card"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid card payload: {reply}") from exc

    async def on_event(self, event: GameEvent) -> None:
        await self._stream.send(
            {"kind": "event", "data": JsonCodec.encode_event(event)}
        )

    async def close(self) -> None:
        await self._stream.close()

    async def _request(self, action: str, **payload: Any) -> dict[str, Any]:
        await self._stream.send({"kind": "request", "action": action, **payload})
        response = await self._stream.receive()
        if response.get("kind") != "response":
            raise ValueError(f"Expected response packet, got: {response}")
        return response
