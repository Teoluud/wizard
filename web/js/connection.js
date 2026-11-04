/** The WebSocket to the server. Packets are handled one at a time, in order,
 * so the page can pause between events (see `GameState.applyEvent`). */
export class Connection {
    /**
     * @param {{onPacket: (packet: object) => Promise<void> | void,
     *          onClose: (reason:string) => void}} handlers
     */
    constructor(handlers) {
        this.handlers = handlers;
        this.ws = null;
        this.queue = [];
        this.pumping = false;
        this.closed = null;
    }
    
    connect(name) {
        const scheme = location.protocol === "https:" ? "wss" : "ws";
        this.ws = new WebSocket(`${scheme}://${location.host}/ws`);
        this.ws.onopen = () => this.send({ kind: "join", name });
        this.ws.onmessage = (event) => {
            this.queue.push(JSON.parse(event.data));
            this.pump();
        };
        this.ws.onclose = () => {
            this.closed = "The connection to the server was lost.";
            this.pump();
        };
    }

    send(packet) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(packet));
        }
    }

    close() {
        if (this.ws) this.ws.close();
    }

    async pump() {
        if (this.pumping) return;
        this.pumping = true;
        try {
            while (this.queue.length > 0) {
                try {
                    await this.handlers.onPacket(this.queue.shift());
                } catch (error) {
                    console.error("Could not handle a packet", error);
                }
            }
        } finally {
            this.pumping = false;
        }
        if (this.closed !== null) {
            const reason = this.closed;
            this.closed = null;
            this.handlers.onClose(reason);
        }
    }
}