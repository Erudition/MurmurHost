import * as WebSocket from "ws";
import { bind } from "decko";
import { error, info } from "winston";
import { dump, uuid } from "hyrest";
import { external, inject, initialize } from "tsdi";
import { AudioOutput } from "../audio-output";
import { AudioCache } from "../audio-cache";
import { Mumble } from "../mumble";
import { Database } from "../database";
import { CachedAudio } from "../../common/models/cached-audio";
import { LiveEvent } from "../../common/models/live-event";
import { QueueItem } from "../../common/models/queue-item";
import { Token } from "../../common/models/token";
import { MumbleConnectionStatus } from "../../common/mumble-connection-status";
import { live } from "../../common/scopes";

interface Authorization {
    token: Token;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function isAuthorization(arg: any): arg is Authorization {
    if (typeof arg !== "object") {
        return false;
    }
    if (typeof arg.token !== "object") {
        return false;
    }
    if (typeof arg.token.id !== "string") {
        return false;
    }
    if (uuid(arg.token.id).error) {
        return false;
    }
    return true;
}

@external
export class LiveWebsocket {
    @inject private readonly audioOutput!: AudioOutput;
    @inject private readonly audioCache!: AudioCache;
    @inject private readonly db!: Database;
    @inject private readonly mumble!: Mumble;

    private ws: WebSocket;
    private authorized = false;

    constructor(ws: WebSocket) {
        this.ws = ws;
    }

    @initialize
    protected initialize(): void {
        this.audioOutput.on("clear", this.handleQueueClear);
        this.audioOutput.on("push", this.handleQueuePush);
        this.audioOutput.on("shift", this.handleQueueShift);
        this.audioCache.on("add", this.handleCacheAdd);
        this.audioCache.on("remove", this.handleCacheRemove);
        this.mumble.on("status change", this.handleMumbleStatusChange);
        this.ws.on("close", this.stop);
        this.ws.on("message", this.handleWsMessage);
    }

    @bind private async handleMumbleStatusChange({ status }: { status: MumbleConnectionStatus }): Promise<void> {
        this.send(new LiveEvent("mumble status change", status));
    }

    @bind private async handleWsMessage(data: string): Promise<void> {
        try {
            const authorization = JSON.parse(data);
            if (!isAuthorization(authorization)) {
                this.terminate();
                info(`Received malformed authorization from websocket.`);
                return;
            }
            const token = await this.db.getRepository(Token).findOne(authorization.token.id);
            if (!token) {
                this.terminate();
                info(`Received unknown token from websocket.`);
                return;
            }
            this.authorized = true;
            this.send(new LiveEvent("init", this.audioOutput.queue, this.audioCache.all));
            this.send(new LiveEvent("mumble status change", this.mumble.status));
        } catch (err) {
            info(`Received malformed message from websocket.`);
        }
    }

    @bind private handleQueueShift(queueItem: QueueItem): void {
        this.send(new LiveEvent("queue shift", queueItem));
    }

    @bind private handleQueuePush(queueItem: QueueItem): void {
        this.send(new LiveEvent("queue push", queueItem));
    }

    @bind private handleCacheAdd(cachedAudio: CachedAudio): void {
        this.send(new LiveEvent("cache add", cachedAudio));
    }

    @bind private handleCacheRemove(cachedAudio: CachedAudio): void {
        this.send(new LiveEvent("cache remove", cachedAudio));
    }

    @bind private handleQueueClear(): void {
        this.send(new LiveEvent("queue clear"));
    }

    @bind private stop(): void {
        this.audioOutput.removeListener("clear", this.handleQueueClear);
        this.audioOutput.removeListener("shift", this.handleQueueShift);
        this.audioOutput.removeListener("push", this.handleQueuePush);
        this.audioCache.removeListener("add", this.handleCacheAdd);
        this.audioCache.removeListener("remove", this.handleCacheRemove);
        this.mumble.removeListener("status change", this.handleMumbleStatusChange);
    }

    private terminate(): void {
        this.ws.close();
        this.stop();
    }

    private send(event: LiveEvent): void {
        if (!this.authorized) {
            return;
        }
        try {
            this.ws.send(JSON.stringify(dump(live, event)));
        } catch (err) {
            error("Error sending packet to live queue websocket:", err);
        }
    }
}

export function createLiveWebsocket(ws: WebSocket): LiveWebsocket {
    return new LiveWebsocket(ws);
}
