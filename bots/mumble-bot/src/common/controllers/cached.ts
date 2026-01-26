import { notFound, controller, route, param, is, uuid, ok } from "hyrest";
import { component, inject } from "tsdi";
import { AudioCache } from "../../server/audio-cache";
import { CachedAudio } from "../models/cached-audio";
import { world } from "../scopes";

@controller
@component
export class Cached {
    @inject private readonly cache!: AudioCache;

    /**
     * Fetch a list of all cached audios.
     */
    @(route("GET", "/cached").dump(CachedAudio, world))
    public async listCached(): Promise<CachedAudio[]> {
        return ok(this.cache.sorted);
    }

    @route("DELETE", "/cached/:id")
    public async deleteCached(@param("id") @(is().validate(uuid)) id: string): Promise<void> {
        if (this.cache.remove(id)) {
            return ok();
        }
        return notFound<undefined>(`No cached sound with id "${id}" found.`);
    }
}
