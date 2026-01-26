import { PrimaryGeneratedColumn, Entity, ManyToOne, Column } from "typeorm";
import { is, scope, specify, uuid } from "hyrest";
import { world, createPlaylist, listPlaylists } from "../scopes";
// eslint-disable-next-line import/no-cycle
import { Playlist } from "./playlist";
// eslint-disable-next-line import/no-cycle
import { Sound } from "./sound";

@Entity()
export class PlaylistEntry {
    @PrimaryGeneratedColumn("uuid")
    @scope(world, listPlaylists)
    @(is().validate(uuid))
    public id?: string;

    @ManyToOne(() => Sound, (sound) => sound.playlistEntrys)
    @is()
    @scope(world, createPlaylist, listPlaylists)
    @specify(() => Sound)
    public sound?: Sound;

    @ManyToOne(() => Playlist, (playlist) => playlist.entries)
    @is()
    @scope(world)
    @specify(() => Playlist)
    public playlist?: Playlist;

    @Column("integer")
    @is()
    @scope(world, createPlaylist, listPlaylists)
    public position?: number;

    @Column("integer", { default: 0 })
    @is()
    @scope(world, createPlaylist, listPlaylists)
    public pitch?: number;

    @Column("integer", { default: 0 })
    @is()
    @scope(world, createPlaylist, listPlaylists)
    public echo?: number;
}
