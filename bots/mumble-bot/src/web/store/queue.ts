import { EventEmitter } from "events";
import { observable, action, computed } from "mobx";
import { bind } from "decko";
import { component, inject } from "tsdi";
import { UsersStore } from "./users";
import { QueueItem } from "../../common/models/queue-item";
import { PlaylistsStore } from "./playlists";
import { SoundsStore } from "./sounds";

@component
export class QueueStore extends EventEmitter {
    @inject private readonly usersStore!: UsersStore;
    @inject private readonly soundsStore!: SoundsStore;
    @inject private readonly playlistsStore!: PlaylistsStore;

    @observable public queue: QueueItem[] = [];
    @observable public currentItem: QueueItem;
    @observable public maxDurationSinceLastClear = 0;

    @computed public get totalSeconds(): number {
        const currentDuration = this.currentItem ? this.currentItem.duration : 0;
        return this.queue.reduce((result, queueItem) => result + queueItem.duration, currentDuration);
    }

    @bind @action public async add(queueItem: QueueItem): Promise<void> {
        queueItem.user = this.usersStore.byId(queueItem.user.id);
        if (queueItem.sound) {
            queueItem.sound = await this.soundsStore.byId(queueItem.sound.id);
        }
        if (queueItem.cachedAudio) {
            queueItem.cachedAudio.user = this.usersStore.byId(queueItem.cachedAudio.user.id);
        }
        if (queueItem.playlist) {
            queueItem.playlist = await this.playlistsStore.byId(queueItem.playlist.id);
        }
        this.queue.push(queueItem);
        this.maxDurationSinceLastClear = Math.max(this.maxDurationSinceLastClear, this.totalSeconds);
    }

    @bind @action public shift(): void {
        this.currentItem = this.queue.shift();
        if (this.queue.length === 0) {
            this.maxDurationSinceLastClear = 0;
        }
    }

    @bind @action public clear(): void {
        this.queue = [];
    }
}
