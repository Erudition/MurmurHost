import { context, body, controller, route, created, badRequest } from "hyrest";
import { component, inject } from "tsdi";
import { verbose } from "winston";
import { world, enqueue } from "../scopes";
import { Context } from "../context";
import { AudioCache } from "../../server/audio-cache";
import { AudioOutput } from "../../server/audio-output";
import { Database } from "../../server/database";
import { Playlist } from "../models/playlist";
import { QueueItem } from "../models/queue-item";
import { Sound } from "../models/sound";

@controller
@component
export class Queue {
    @inject private readonly audioOutput!: AudioOutput;
    @inject private readonly audioCache!: AudioCache;
    @inject private readonly db!: Database;

    @(route("POST", "/queue").dump(QueueItem, world))
    public async enqueue(@body(enqueue) queueItem: QueueItem, @context ctx?: Context): Promise<QueueItem> {
        switch (queueItem.type) {
            case "sound": {
                if (!queueItem.sound) {
                    return badRequest<QueueItem>(`Must specify "sound" if type is set to "sound".`);
                }
                const sound = await this.db.getRepository(Sound).findOne(queueItem.sound.id);
                if (!sound) {
                    return badRequest<QueueItem>(`No sound with id "${queueItem.sound.id}".`);
                }
                sound.used++;
                await this.db.getRepository(Sound).save(sound);
                break;
            }
            case "cached audio": {
                if (!queueItem.cachedAudio) {
                    return badRequest<QueueItem>(`Must specify "cachedAudio" if type is set to "cached audio".`);
                }
                if (!this.audioCache.hasId(queueItem.cachedAudio.id)) {
                    return badRequest<QueueItem>(`No cached audio with id "${queueItem.cachedAudio.id}".`);
                }
                break;
            }
            case "playlist": {
                if (!queueItem.playlist) {
                    return badRequest<QueueItem>(`Must specify "playlist" if type is set to "playlist".`);
                }
                const playlist = await this.db.getRepository(Playlist).findOne(queueItem.playlist.id);
                if (!playlist) {
                    return badRequest<QueueItem>(`No playlist with id "${queueItem.playlist.id}".`);
                }
                playlist.used++;
                await this.db.getRepository(Playlist).save(playlist);
                break;
            }
        }
        const currentUser = await ctx.currentUser();
        queueItem.created = new Date();
        queueItem.user = currentUser;

        this.audioOutput.enqueue(queueItem);
        verbose(`User ${currentUser.name} enqueued ${queueItem.type} #${queueItem.relevantId}.`);

        return created(queueItem);
    }
}
