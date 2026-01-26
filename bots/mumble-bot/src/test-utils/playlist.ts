import { Playlist } from "../common/models/playlist";
import { PlaylistEntry } from "../common/models/playlist-entry";
import { Sound } from "../common/models/sound";
import { User } from "../common/models/user";
import { Database } from "../server/database";

const defaultPlaylist = {
    description: "A Playlist",
};

export async function createPlaylist(
    creator: User,
    pitch: number,
    data: Playlist,
    ...sounds: Sound[]
): Promise<Playlist> {
    const playlist = await tsdi
        .get(Database)
        .getRepository(Playlist)
        .save(
            Object.assign(new Playlist(), {
                ...defaultPlaylist,
                ...data,
                creator,
            }),
        );
    await Promise.all(
        sounds.map(async (sound, position) => {
            await tsdi.get(Database).getRepository(PlaylistEntry).save({
                sound,
                position,
                playlist,
                pitch,
            });
        }),
    );
    return await tsdi
        .get(Database)
        .getRepository(Playlist)
        .findOne({
            where: { id: playlist.id },
            relations: ["creator", "entries", "entries.sound"],
        });
}
