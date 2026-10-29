"""Network client for Wizard.

Example:
    python -m src.network.client --name John
"""

import argparse
import asyncio
from typing import Any, Mapping

from src.backend.agents import PlayerAgent, GameObserver
from src.backend.cards import Card
from src.backend.events import GameOver
from src.frontend.network_cli import NetworkCliAgent
from src.network.protocol import JsonCodec, JsonStream


class GameClient:
    """Connects to a `GameServer` and delegates decisions to a local `PlayerAgent`."""

    def __init__(self, host: str, port: int, name: str, agent: PlayerAgent) -> None:
        self.host = host
        self.port = port
        self.name = name
        self.agent = agent

    async def run(self) -> None:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        stream = JsonStream(reader, writer)
        try:
            await stream.send({"kind": "join", "name": self.name})
            reply = await stream.receive()
            if reply.get("kind") == "error":
                raise RuntimeError(f"Server rejected join: {reply.get('message')}")
            print(reply.get("message", "Connected to server."))

            while True:
                packet = await stream.receive()
                kind = packet.get("kind")
                if kind == "event":
                    event = JsonCodec.decode_event(packet["data"])
                    if isinstance(self.agent, GameObserver):
                        await self.agent.on_event(event)
                    if isinstance(event, GameOver):
                        break
                elif kind == "request":
                    response = await self._handle_request(packet)
                    await stream.send(response)
                elif kind == "error":
                    raise RuntimeError(f"Server error: {packet.get('message')}")
        finally:
            await stream.close()

    async def _handle_request(self, packet: Mapping[str, Any]) -> dict[str, Any]:
        action = packet["action"]
        view = JsonCodec.decode_view(packet["view"])

        match action:
            case "ask_trump_color":
                color = await self.agent.ask_trump_color(view)
                return {"kind": "response", "color": color.value}
            case "ask_call":
                forbidden = packet.get("forbidden_call")
                call = await self.agent.ask_call(view, forbidden)
                return {"kind": "response", "call": call}
            case "ask_card_to_pass":
                rule = JsonCodec.decode_pass_rule(packet["rule"])
                recipient = str(packet["recipient"])
                cards = await self.agent.ask_card_to_pass(view, rule, recipient)
                return {"kind": "response", "cards": [c.to_dict() for c in cards]}
            case "ask_card":
                legal_cards = [Card.from_dict(c) for c in packet["legal_cards"]]
                card = await self.agent.ask_card(view, legal_cards)
                return {"kind": "response", "card": card.to_dict()}
            case _:
                raise ValueError(f"Unknown server request action: {action}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect to a Wizard server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--name", required=True, help="your player name")
    args = parser.parse_args()

    client = GameClient(
        host=args.host,
        port=args.port,
        name=args.name,
        agent=NetworkCliAgent(),
    )
    asyncio.run(client.run())


if __name__ == "__main__":
    main()
