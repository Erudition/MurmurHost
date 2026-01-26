import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, inject } from "tsdi";
import { SoundsStore } from "./sounds";
import { UsersStore } from "./users";
import { Playlists, PlaylistsQuery } from "../../common/controllers/playlists";
import { Queue } from "../../common/controllers/queue";
import { Playlist } from "../../common/models/playlist";
import { PlaylistEntry } from "../../common/models/playlist-entry";
import { PlaylistsQueryResult } from "../../common/models/playlists-query-result";
import { QueueItem } from "../../common/models/queue-item";
import { Sound } from "../../common/models/sound";

@component
export class PlaylistsStore {
    @inject private readonly playlistsController!: Playlists;
    @inject private readonly soundsStore!: SoundsStore;
    @inject private readonly usersStore!: UsersStore;
    @inject private readonly queue!: Queue;

    @observable public playlists = new Map<string, Playlist>();
    @observable public loading = true;
    @observable public quickList: PlaylistEntry[] = [];

    @bind @action public async query(query: PlaylistsQuery): Promise<PlaylistsQueryResult> {
        const result = await this.playlistsController.queryPlaylists(query);
        await Promise.all(
            result.playlists.map(async (playlist) => {
                playlist.creator = this.usersStore.byId(playlist.creator.id);
                for (const entry of playlist.entries) {
                    entry.sound = await this.soundsStore.byId(entry.sound.id);
                }
            }),
        );
        result.playlists.forEach((playlist) => this.playlists.set(playlist.id, playlist));
        return result;
    }

    @computed public get all(): Playlist[] {
        return Array.from(this.playlists.values());
    }

    @bind public async byId(id: string): Promise<Playlist> {
        if (this.playlists.has(id)) {
            return this.playlists.get(id);
        }
        const playlist = await this.playlistsController.getPlaylist(id);
        this.playlists.set(id, playlist);
        return playlist;
    }

    @bind @action public async play(playlist: Playlist): Promise<void> {
        await this.queue.enqueue({
            type: "playlist",
            playlist: { id: playlist.id },
        } as QueueItem);
        playlist.used++;
    }

    @bind @action public addQuickEntry(sound: Sound): void {
        const { pitch } = this.soundsStore;
        this.quickList.push({
            sound,
            pitch,
        });
    }

    @bind @action public async playQuickList(): Promise<void> {
        for (const { sound, pitch } of this.quickList) {
            await this.queue.enqueue({
                type: "sound",
                sound: { id: sound.id },
                pitch,
            } as QueueItem);
        }
    }

    @bind @action public clearQuickList(): void {
        this.quickList = [];
    }

    @bind @action public removeQuickListEntry(index: number): void {
        this.quickList.splice(index, 1);
    }

    @bind @action public async saveQuickList(description: string): Promise<void> {
        const playlist = await this.playlistsController.createPlaylist({
            description,
            entries: this.quickList.map(({ pitch, sound, echo }, position) => ({
                position,
                sound: { id: sound.id },
                pitch,
                echo,
            })),
        } as Playlist);
        this.playlists.set(playlist.id, await this.mapSounds(playlist));
        this.quickList = [];
    }

    private async mapSounds(playlist: Playlist): Promise<Playlist> {
        playlist.entries = await Promise.all(
            playlist.entries.map(async (entry) => ({
                ...entry,
                sound: await this.soundsStore.byId(entry.sound.id),
            })),
        );
        return playlist;
    }

    @bind @action public async update(id: string, playlist: Playlist): Promise<void> {
        const newPlaylist = await this.mapSounds(await this.playlistsController.updatePlaylist(id, playlist));
        this.playlists.set(id, newPlaylist);
    }
}
