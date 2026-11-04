import { cardKey } from "./cards.js";
import { Connection } from "./connection.js";
import { renderDisconnected, renderGame, renderJoin, renderLobby } from "./render.js";
import { GameState } from "./state.js";

const root = document.getElementById("app");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fast = new URLSearchParams(location.search).has("fast");

let connection = null;
let state = null;
let prompt = null;
let inGame = null;

function showJoin(error = null) {
    inGame = false;
    renderJoin(root, { error, onJoin: join });
}

function join(name) {
    state = new GameState(name, fast);
    prompt = null;
    connection = new Connection({ onPacket: handlePacket, onClose: handleClose });
    connection.connect(name);
    renderLobby(root, "Connecting...");
}

function handleClose(reason) {
    if (state && state.final) return; // the game is over: closing is normal
    renderDisconnected(root, reason);
}

async function handlePacket(packet) {
    switch (packet.kind) {
        case "welcome":
            renderLobby(root, packet.message);
            break;
        case "error":
            connection.close();
            showJoin(packet.message);
            break;
        case "event":
            await handleEvent(packet.data);
            break;
        case "request":
            handleRequest(packet);
            break;
    }
}

async function handleEvent(event) {
    const delay = state.applyEvent(event);
    inGame = true;
    paint();
    if (delay > 0) await sleep(delay);
    if (event.event === "trick_won") {
        state.finishTrick();
        paint();
    }
}

function paint() {
    if (inGame) renderGame(root, state, prompt);
}

/** Sends the answer to the question and goes back to watching. */
function answer(fields) {
    connection.send({ kind: "response", ...fields });
    prompt = null;
    paint();
}

function handleRequest(packet) {
    state.syncView(packet.view);
    inGame = true;
    switch (packet.action) {
        case "ask_trump_color":
            prompt = { kind: "trump", onPick: (color) => answer({ color }) };
            break;
        case "ask_call":
            prompt = {
                kind: "call",
                max: packet.view.round_number,
                forbidden: packet.forbidden_call,
                hidden: state.handHidden,
                onPick: (call) => answer({ call }),
            };
            break;
        case "ask_card_to_pass":
            prompt = passPrompt(packet);
            break;
        case "ask_card":
            prompt = cardPrompt(packet);
            break;
        default:
            console.error("Unknown request", packet.action);
            return;
    }
    paint();
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

function cardPrompt(packet) {
    return {
        kind: "card",
        legal: new Set(packet.legal_cards.map(cardKey)),
        hidden: state.handHidden,
        onPlay: (card) => answer({ card }),
        onPlayHidden: () => answer({ card: packet.legal_cards[0] }),
    };
}

function passPrompt(packet) {
    const { count, direction } = packet.rule;
    const selected = new Set();
    return {
        kind: "pass",
        count,
        direction,
        recipient: packet.recipient,
        selected,
        onToggle(index) {
            if (selected.has(index)) selected.delete(index);
            else if (selected.size < count) selected.add(index);
            paint();
        },
        onConfirm() {
            answer({ cards: [...selected].map((i) => state.hand[i]) });
        },
    };
}

showJoin();