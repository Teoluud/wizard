import { cardKey, sortHand } from "./cards.js";

const MAX_LOG = 40;

/** How long (ms) the page lingers on each kind of event so people can follow. */
const DELAYS = {
    round_started: 800,
    trump_chosen: 600,
    call_made: 400,
    cards_passed: 700,
    card_played: 650,
    trick_won: 1700,
    round_scored: 1800,
};

/** Everything the page knows about the game, built from events and views. */
export class GameState {
    constructor(me, fast = false) {
        this.me = me;
        this.fast = fast;
        this.seats = [];
        this.nRounds = 0;
        this.round = 0;
        this.dealer = null;
        this.trump = null;
        this.statuses = new Map();
        this.table = [];
        this.winner = null;
        this.hand = [];
        this.others = [];
        this.handHidden = false;
        this.log = [];
        this.final = null;
    }

    status(name) {
        if (!this.statuses.has(name)) {
            this.statuses.set(name, { call: null, tricks: 0, points: 0, cards: 0 });
        }
        return this.statuses.get(name);
    }

    say(text) {
        this.log.push(text);
        if (this.log.length > MAX_LOG) this.log.shift();
    }

    /** Takes over what a view says: it is always right about the present. */
    syncView(view) {
        this.round = view.round_number;
        this.dealer = view.dealer_name;
        this.trump = view.trump;
        this.table = view.table.map(([player, card]) => ({ player, card }));
        for (const p of view.players) {
            Object.assign(this.status(p.name), {
                call: p.call,
                tricks: p.tricks_won,
                points: p.points,
                cards: p.card_count,
            });
        }
        const own = view.hands.find(([owner]) => owner === this.me);
        this.handHidden = own === undefined;
        this.hand = own ? sortHand(own[1]) : [];
        this.others = view.hands
            .filter(([owner]) => owner !== this.me)
            .map(([owner, cards]) => ({ owner, cards: sortHand(cards) }));
    }

    /** Applies an event; returns how long the page should wait before the next. */
    applyEvent(ev) {
        switch (ev.event) {
            case "game_started":
                this.seats = ev.players;
                this.nRounds = ev.n_rounds;
                ev.players.forEach((name) => this.status(name));
                this.say(`Game of ${ev.n_rounds} rounds: ${ev.players.join(", ")}`);
                break;
            case "round_started":
                this.round = ev.round_number;
                this.dealer = ev.dealer;
                this.trump = ev.trump;
                this.table = [];
                this.winner = null;
                this.hand = [];
                this.others = [];
                this.handHidden = false;
                for (const s of this.statuses.values()) Object.assign(s, { call: null, tricks: 0 });
                this.say(`Round ${ev.round_number}, dealer ${ev.dealer}`);
                break;
            case "trump_chosen":
                this.trump = { ...this.trump, color: ev.color };
                this.say(`${ev.dealer} chose ${ev.color} as trump`);
                break;
            case "call_made":
                this.status(ev.player).call = ev.call;
                this.say(`${ev.player} called ${ev.call}`);
                break;
            case "cards_passed":
                this.say(`Everybody passed ${ev.count} cards to the ${ev.direction}`);
                break;
            case "card_played":
                this.table.push({ player: ev.player, card:ev.card });
                this.removeCard(ev.player, ev.card);
                break;
            case "trick_won":
                this.winner = ev.winner;
                this.status(ev.winner).tricks += 1;
                this.say(`${ev.winner} wins the trick`);
                break;
            case "round_scored":
                for (const s of ev.scores) this.status(s.name).points = s.points;
                this.say(
                    `Round ${ev.round_number} scored: ` +
                    ev.scores.map((s) => `${s.name} ${s.points}`).join(", ")
                );
                break;
            case "game_over":
                this.final = [...ev.scores].sort((a, b) => b.points - a.points);
                break;
        }
        return this.fast ? 0 : DELAYS[ev.event] ?? 0;
    }

    /** Called once the page has shown the result of a trick for a while. */
    finishTrick() {
        this.table = [];
        this.winner = null;
    }

    removeCard(player, card) {
        const gone = (list) => {
            const at = list.findIndex((c) => cardKey(c) === cardKey(card));
            if (at >= 0) list.splice(at, 1);
        };
        if (player === this.me) gone(this.hand);
        const other = this.others.find((o) => o.owner === player);
        if (other) gone(other.cards);
    }
}