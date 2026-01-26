import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, initialize, inject } from "tsdi";
import { TagsStore } from "./tags";
import { CachedAudioStore } from "./cached-audio";
import { LoginStore } from "./login";
import { Favorites } from "../../common/controllers/favorites";
import { Queue } from "../../common/controllers/queue";
import { Sounds, SoundsQuery } from "../../common/controllers/sounds";
import { CachedAudio } from "../../common/models/cached-audio";
import { Favorite } from "../../common/models/favorite";
import { QueueItem } from "../../common/models/queue-item";
import { Sound } from "../../common/models/sound";
import { SoundsQueryResult } from "../../common/models/sounds-query-result";
import { Tag } from "../../common/models/tag";
import { User } from "../../common/models/user";

@component
export class SoundsStore {
    @inject private readonly soundsController!: Sounds;
    @inject private readonly favoritesController!: Favorites;
    @inject private readonly queue!: Queue;
    @inject private readonly tags!: TagsStore;
    @inject private readonly cachedAudio!: CachedAudioStore;
    @inject private readonly login!: LoginStore;

    @observable public sounds = new Map<string, Sound>();
    @observable public pitch = 0;
    @observable public echo = 0;
    @observable public favorites: Favorite[] = [];

    @computed public get all(): Sound[] {
        return Array.from(this.sounds.values());
    }

    @initialize
    protected async initialize(): Promise<void> {
        if (this.login.loggedIn) {
            this.favorites = await this.favoritesController.getFavorites(this.login.userId);
            await Promise.all(this.favorites.map(async ({ sound }) => await this.byId(sound.id)));
        }
    }

    @bind @action public async toggleFavorite(id: string): Promise<void> {
        const existing = this.favorites.find((favorite) => favorite.sound.id === id);
        if (existing) {
            await this.favoritesController.deleteFavorite(existing.id);
            this.favorites = this.favorites.filter((favorite) => favorite.id !== existing.id);
        } else {
            const favorite = await this.favoritesController.createFavorite({
                sound: { id } as Sound,
                user: { id: this.login.userId } as User,
            });
            this.favorites.push(favorite);
        }
    }

    @bind public isFavorite(id: string): boolean {
        return this.favorites.some((favorite) => favorite.sound?.id === id);
    }

    @bind @action public async untag(sound: Sound, tag: Tag): Promise<void> {
        this.sounds.set(sound.id, await this.soundsController.untagSound(sound.id, tag.id));
    }

    @bind @action public async tag(sound: Sound, tagIdOrName: string): Promise<void> {
        if (!this.tags.byId(tagIdOrName)) {
            const tag = await this.tags.createTag(tagIdOrName);
            this.sounds.set(sound.id, await this.soundsController.tagSound(sound.id, { id: tag.id }));
            return;
        }
        this.sounds.set(sound.id, await this.soundsController.tagSound(sound.id, { id: tagIdOrName }));
    }

    @bind @action public async update(id: string, sound: Sound): Promise<void> {
        this.sounds.set(id, await this.soundsController.updateSound(id, sound));
    }

    @bind @action public async delete(id: string): Promise<void> {
        this.sounds.set(id, await this.soundsController.deleteSound(id));
    }

    @bind @action public async play(sound: Sound): Promise<void> {
        await this.queue.enqueue({
            type: "sound",
            sound: { id: sound.id },
            pitch: this.pitch,
            echo: this.echo,
        } as QueueItem);
        sound.used++;
        this.sounds.set(sound.id, sound);
    }

    @bind @action public async query(query: SoundsQuery): Promise<SoundsQueryResult> {
        const result = await this.soundsController.querySounds(query);
        result.sounds.forEach((sound) => this.sounds.set(sound.id, sound));
        return result;
    }

    @bind public async byId(id: string): Promise<Sound> {
        if (this.sounds.has(id)) {
            return this.sounds.get(id);
        }
        const sound = await this.soundsController.getSound(id);
        this.sounds.set(id, sound);
        return sound;
    }

    @bind @action public async save({ id }: CachedAudio, description?: string): Promise<Sound> {
        const sound = await this.soundsController.save({ id });
        if (description) {
            await this.soundsController.updateSound(sound.id, { description } as Sound);
        }
        this.sounds.set(sound.id, sound);
        this.cachedAudio.remove({ id });
        return sound;
    }

    @bind public async fork(
        { id }: Sound,
        overwrite: boolean,
        description: string,
        start: number,
        end: number,
    ): Promise<Sound> {
        const forkedSound = await this.soundsController.forkSound(id, {
            description,
            overwrite,
            actions: [{ action: "crop", start, end }],
        });
        this.sounds.set(forkedSound.id, forkedSound);
        const original = this.sounds.get(id);
        this.sounds.set(id, await this.soundsController.getSound(original.id));
        return forkedSound;
    }

    @bind public async rate(id: string, stars: number): Promise<Sound> {
        const ratedSound = await this.soundsController.rateSound(id, { stars });
        this.sounds.set(id, ratedSound);
        return ratedSound;
    }
}
