import { cardKey, cardNode, COLORS, trumpNode } from "./cards.js";
import { h } from "./dom.js";

const SAVED_NAME = "wizard-name";

export function savedName() {
    try {
        return localStorage.getItem(SAVED_NAME) ?? "";
    } catch {
        return "";
    }
}

function rememberName(name) {
    try {
        localStorage.setItem(SAVED_NAME, name);
    } catch {
        /* private mode: not important */
    }
}

/** The first screen: who are you? */
export function renderJoin(root, { error, onJoin }) {
    const input = h("input", {
        id: "name",
        maxlength: "20",
        value: savedName(),
        placeholder: "Your name",
        autofocus: true,
    });
    const submit = (event) => {
        event.preventDefault();
        const name = input.value.trim();
        if (!name) return;
        rememberName(name);
        onJoin(name);
    };
    root.replaceChildren(
        h(
            "form",
            { class: "panel join", onsubmit: submit },
            h("h1", {}, "Wizard"),
            h("label", { for: "name" }, "Choose a name to join the table"),
            input,
            h("button", { type: "submit", class: "primary" }, "Join"),
            error ? h("p", { class: "error", role: "alert" }, error) : null
        )
    );
    input.focus();
}

export function renderLobby(root, message) {
    root.replaceChildren(
        h(
            "div",
            { class: "panel join" },
            h("h1", {}, "Wizard"),
            h("p", { class: "waiting" }, message || "Waiting for the other players..."),
            h("p", { class: "hint" }, "The game starts when the table is full.")
        )
    );
}

export function renderDisconnected(root, reason) {
    root.replaceChildren(
        h(
            "div",
            { class: "panel join" },
            h("h1", {}, "Wizard"),
            h("p", { class: "error", role: "alert" }, reason),
            h("button", { class: "primary", onclick: () => location.reload() }, "Reload")
        )
    );
}

/** The whole game screen, rebuilt from the state and the current question. */
export function renderGame(root, state, prompt) {
    root.replaceChildren(
        ...[
            header(state),
            h(
                "div",
                { class: "layout" },
                h("section", { class: "table-area" }, scoreboard(state), felt(state)),
                h("aside", { class: "log" }, h("h2", {}, "Log"), logList(state))
            ),
            othersCards(state),
            promptPanel(state, prompt),
            handPanel(state, prompt),
            state.final ? finalOverlay(state) : null,
        ].filter((node) => node !== null)
    );
    const log = root.querySelector(".log ul");
    if (log) log.scrollTop = log.scrollHeight;
}

function header(state) {
    const total = state.nRounds ? ` of ${state.nRounds}` : "";
    return h(
        "header",
        {},
        h("strong", {}, `Round ${state.round}${total}`),
        h("span", {}, `Dealer: ${state.dealer ?? "-"}`),
        h("span", { class: "trump" }, "Trump: ", state.trump ? trumpNode(state.trump) : "-")
    );
}

function scoreboard(state) {
    const rows = state.seats.map((name) => {
        const s = state.status(name);
        return h(
            "tr",
            { class: name === state.me ? "me" : "" },
            h(
                "th",
                { scope: "row" },
                name,
                name === state.me ? " (you)" : "",
                name === state.dealer ? " ◆" : ""
            ),
            h("td", {}, s.call ?? "-"),
            h("td", {}, s.tricks),
            h("td", {}, s.points)
        );
    });
    return h(
        "table",
        { class: "scores" },
        h(
            "thead",
            {},
            h(
                "tr",
                {},
                h("th", {}, "Player"),
                h("th", {}, "Call"),
                h("th", {}, "Won"),
                h("th", {}, "Points")
            )
        ),
        h("tbody", {}, rows)
    );
}

function felt(state) {
    const plays = state.table.map(({ player, card }) =>
        h(
            "figure",
            { class: player === state.winner ? "play winner" : "play" },
            cardNode(card),
            h("figcaption", {}, player === state.winner ? `${player} wins!` : player)
        )
    );
    return h(
        "div",
        { class: "felt", "aria-live": "polite" },
        plays.length ? plays : h("p", { class: "hint" }, "No cards on the table")
    );
}

function logList(state) {
    return h("ul", {}, state.log.slice(-14).map((line) => h("li", {}, line)));
}

function othersCards(state) {
    const visible = state.others.filter((o) => o.cards.length > 0);
    if (visible.length === 0) return null;
    return h(
        "section",
        { class: "others" },
        visible.map((o) =>
            h(
                "div",
                { class: "other" },
                h("span", {}, `${o.owner}'s cards`),
                o.cards.map((c) => cardNode(c))
            )
        )
    );
}

function promptPanel(state, prompt) {
    if (!prompt) {
        return h("section", { class: "prompt idle" }, h("p", {}, "Waiting for the other players..."));
    }
    switch (prompt.kind) {
        case "trump":
            return h(
                "section",
                { class: "prompt" },
                h("p", {}, "The trump card is a Wizard. You are the dealer: choose the trump suit."),
                h(
                    "div",
                    { class: "choices" },
                    COLORS.map((color) =>
                        h("button", { class: `choice c-${color}`, onclick: () => prompt.onPick(color) }, color)
                    )
                )
            );
        case "call":
            return callPrompt(prompt);
        case "pass":
            return h(
                "section",
                { class: "prompt" },
                h(
                    "p",
                    {},
                    `Pass ${prompt.count} cards to ${prompt.recipient} (on your ${prompt.direction}): `,
                    `${prompt.selected.size} of ${prompt.count} chosen.`
                ),
                h(
                    "button",
                    {
                        class: "primary",
                        disabled: prompt.selected.size !== prompt.count,
                        onclick: prompt.onConfirm,
                    },
                    "Pass the selected cards"
                )
            );
        case "card":
            return h(
                "section",
                { class: "prompt" },
                prompt.hidden
                    ? [
                        h("p", {}, "You can't see your own card in this round."),
                        h("button", { class: "primary", onclick: prompt.onPlayHidden }, "Play your hidden card"),
                    ]
                    : h("p", {}, "Your turn: choose a card to play.")
            );
        default:
            return null;
    }
}

function callPrompt(prompt) {
    const buttons = [];
    for (let n = 0; n <= prompt.max; n++) {
        const forbidden = n === prompt.forbidden;
        buttons.push(
            h(
                "button",
                {
                    class: "choice number",
                    disabled: forbidden,
                    title: forbidden ? "As the dealer, you can't call this" : false,
                    onclick: () => prompt.onPick(n),
                },
                n
            )
        );
    }
    return h(
        "section",
        { class: "prompt" },
        h("p", {}, "How many tricks do you call?"),
        prompt.hidden ? h("p", { class: "hint" }, "Blind round: you can't see your cards yet.") : null,
        prompt.forbidden !== null
            ? h("p", { class: "hint" }, `You are the dealer: you can't call ${prompt.forbidden}.`)
            : null,
        h("div", { class: "choices" }, buttons)
    );
}

function handPanel(state, prompt) {
    if (state.handHidden) {
        return h(
            "section",
            { class: "hand" },
            h("h2", {}, "Your hand"),
            h("p", { class: "hint" }, "Hidden this round")
        );
    }
    const cards = state.hand.map((card, index) => {
        let mode = "";
        let click = null;
        if (prompt && prompt.kind === "card") {
            const legal = prompt.legal.has(cardKey(card));
            mode = legal ? "playable" : "disabled";
            click = legal ? () => prompt.onPlay(card) : null;
        } else if (prompt && prompt.kind === "pass") {
            mode = prompt.selected.has(index) ? "selected" : "playable";
            click = () => prompt.onToggle(index);
        }
        return cardNode(card, mode, click);
    });
    return h(
        "section",
        { class: "hand" },
        h("h2", {}, "Your hand"),
        cards.length ? h("div", { class: "cards" }, cards) : h("p", { class: "hint" }, "No cards")
    );
}

function finalOverlay(state) {
    const winner = state.final[0];
    return h(
        "div",
        { class: "overlay", role: "dialog", "aria-label": "Final scores" },
        h(
            "div",
            { class: "panel" },
            h("h1", {}, `${winner.name} wins!`),
            h("ol", {}, state.final.map((s) => h("li", {}, `${s.name}: ${s.points} points`))),
            h("button", { class: "primary", onclick: () => location.reload() }, "Play again")
        )
    );
}