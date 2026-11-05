import { h } from "./dom.js";

export const COLORS = ["red", "yellow", "blue", "green"];
const LETTER = { red: "R", yellow: "Y", blue: "B", green: "G" };

export const isWizard = (card) => card.type === "wizard";
export const isJester = (card) => card.type === "jester";

/** Identifies a card by what it is (the two Wizards of a hand are the same). */
export const cardKey = (card) => `${card.type}:${card.number}:${card.color}`;

export function cardLabel(card) {
    if (isWizard(card)) return "Wizard";
    if (isJester(card)) return "Jester";
    return `${card.number} ${card.color}`;
}

/** Wizards first, then each color from high to low, Jesters last. */
export function sortHand(cards) {
    const rank = (c) => (isWizard(c) ? 0 : isJester(c) ? 2 : 1);
    return [...cards].sort(
        (a, b) =>
            rank(a) - rank(b) ||
            String(a.color).localeCompare(String(b.color)) ||
            b.number - a.number
    );
}

/** A card face. `mode` is "", "playable", "disabled" or "selected". */
export function cardNode(card, mode = "", onClick = null) {
    const kind = isWizard(card) ? "wizard" : isJester(card) ? "jester" : card.color;
    const face = isWizard(card) ? "W" : isJester(card) ? "J" : card.number;
    const corner = isWizard(card) || isJester(card) ? "" : LETTER[card.color];
    const node = h(
        "div",
        {
            class: `card c-${kind} ${mode}`,
            title: cardLabel(card),
            role: onClick ? "button" : "img",
            "aria-label": cardLabel(card),
            tabindex: onClick && mode !== "disabled" ? "0" : false,
        },
        h("span", { class: "corner" }, corner),
        h("span", { class: "face" }, face)
    );
    if (onClick && mode !== "disabled") {
        node.addEventListener("click", onClick);
        node.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onClick();
            }
        });
    }
    return node;
}

export function trumpNode(trump) {
    if (!trump || trump.card === null) {
        return h("span", { class: "trump-text" }, "none (last round)");
    }
    if (isJester(trump.card)) return h("span", { class: "trump-text" }, "none (Jester)");
    if (isWizard(trump.card)) {
        return trump.color
        ? h("span", { class: `swatch c-${trump.color}` }, trump.color)
        : h("span", { class: "trump-text" }, "Wizard: dealer picks");
    }
    return cardNode(trump.card, "mini")
}