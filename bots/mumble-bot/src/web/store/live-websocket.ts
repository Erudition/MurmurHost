import { EventEmitter } from "events";
import { observable } from "mobx";
import { populate } from "hyrest";
import { bind } from "decko";
import { component, inject, initialize } from "tsdi";
import { CachedAudioStore } from "./cached-audio";
import { QueueStore } from "./queue";
import { LoginStore } from "./login";
import { LiveEvent } from "../../common/models/live-event";
import { MumbleConnectionStatus } from "../../common/mumble-connection-status";
import { live } from "../../common/scopes";

declare const baseUrl: string;

@component
export class LiveWebsocket extends EventEmitter {
    @inject private readonly loginStore!: LoginStore;
    @inject private readonly cachedAudio!: CachedAudioStore;
    @inject private readonly queue!: QueueStore;

    @observable public loading = true;
    @observable public mumbleStatus = MumbleConnectionStatus.HEALTHY;
    @observable public initialized = false;

    private ws: WebSocket;

    @initialize
    public async initialize(): Promise<void> {
        await this.loginStore.onLogin$.toPromise();
        const websocketUrl = `${baseUrl.replace("http", "ws")}/live`;
        this.ws = new WebSocket(websocketUrl);
        this.ws.addEventListener("message", this.handleMessage);
        this.ws.addEventListener("open", this.handleOpen);
        this.initialized = true;
    }

    @bind private handleOpen(): void {
        this.ws.send(
            JSON.stringify({
                token: { id: this.loginStore.authToken },
            }),
        );
    }

    @bind private async handleInit({ queue, cachedAudios }: LiveEvent): Promise<void> {
        // Needs to be done in order and hence `Promise.all` can't be used.
        for (const queueItem of queue) {
            await this.queue.add(queueItem);
        }
        await Promise.all(cachedAudios.map(this.cachedAudio.add));
        this.loading = false;
    }

    @bind private async handleCacheAdd({ cachedAudio }: LiveEvent): Promise<void> {
        this.cachedAudio.add(cachedAudio);
    }

    @bind private handleCacheRemove({ cachedAudio }: LiveEvent): void {
        this.cachedAudio.remove(cachedAudio);
    }

    @bind private handleQueueShift(): void {
        this.queue.shift();
    }

    @bind private handleQueuePush({ queueItem }: LiveEvent): void {
        this.queue.add(queueItem);
    }

    @bind private handleMumbleStatusChange({ mumbleStatus }: LiveEvent): void {
        this.mumbleStatus = mumbleStatus;
    }

    @bind private handleQueueClear(): void {
        this.queue.clear();
    }

    @bind private handleMessage({ data }: MessageEvent): void {
        const liveEvent = populate(live, LiveEvent, JSON.parse(data));
        switch (liveEvent.event) {
            case "init":
                this.handleInit(liveEvent);
                break;
            case "cache add":
                this.handleCacheAdd(liveEvent);
                break;
            case "cache remove":
                this.handleCacheRemove(liveEvent);
                break;
            case "queue shift":
                this.handleQueueShift();
                break;
            case "queue push":
                this.handleQueuePush(liveEvent);
                break;
            case "queue clear":
                this.handleQueueClear();
                break;
            case "mumble status change":
                this.handleMumbleStatusChange(liveEvent);
                break;
            default:
                break;
        }
        this.emit("event", liveEvent);
    }
}
