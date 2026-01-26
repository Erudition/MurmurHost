import { is, DataType, oneOf, required, scope, specify } from "hyrest";
import { live } from "../scopes";
import { QueueItem } from "./queue-item";
import { MumbleConnectionStatus } from "../mumble-connection-status";
import { CachedAudio } from "./cached-audio";

export type EventName =
    | "init"
    | "cache add"
    | "cache remove"
    | "queue shift"
    | "queue push"
    | "queue clear"
    | "mumble status change";

export class LiveEvent {
    constructor();
    constructor(event: "mumble status change", arg2: MumbleConnectionStatus);
    constructor(event: "cache add" | "cache remove", arg2: CachedAudio);
    constructor(event: "queue shift" | "queue push", arg2: QueueItem);
    constructor(event: "queue clear");
    constructor(event: "init", arg2: QueueItem[], arg3: CachedAudio[]);
    constructor(
        event?: EventName,
        arg2?: QueueItem | CachedAudio | QueueItem[] | MumbleConnectionStatus,
        arg3?: CachedAudio[],
    ) {
        if (!event) {
            return;
        }
        this.event = event;
        switch (event) {
            case "init":
                this.queue = arg2 as QueueItem[];
                this.cachedAudios = arg3;
                break;
            case "cache add":
            case "cache remove":
                this.cachedAudio = arg2 as CachedAudio;
                break;
            case "queue shift":
            case "queue push":
                this.queueItem = arg2 as QueueItem;
                break;
            case "queue clear":
            case "mumble status change":
                this.mumbleStatus = arg2 as MumbleConnectionStatus;
        }
    }

    @(is(DataType.str).validate(
        required,
        oneOf("init", "cache add", "cache remove", "queue shift", "queue push", "queue clear"),
    ))
    @scope(live)
    public event: EventName;

    @(is(DataType.str).validate(required, oneOf("disconnected", "connecting", "error", "healthy")))
    @scope(live)
    public mumbleStatus: MumbleConnectionStatus;

    @is()
    @scope(live)
    public queueItem?: QueueItem;

    @is()
    @scope(live)
    public cachedAudio?: CachedAudio;

    @is()
    @specify(() => QueueItem)
    @scope(live)
    public queue?: QueueItem[];

    @is()
    @specify(() => CachedAudio)
    @scope(live)
    public cachedAudios?: CachedAudio[];
}
