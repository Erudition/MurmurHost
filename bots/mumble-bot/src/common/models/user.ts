import { Column, PrimaryGeneratedColumn, Entity, OneToMany } from "typeorm";
import { is, scope, specify, length, uuid, transform, only, required, precompute } from "hyrest";
import {
    listRatings,
    rateSound,
    live,
    world,
    login,
    owner,
    signup,
    createMumbleLink,
    listPlaylists,
    updateUser,
    statistics,
    createFavorite,
    linkTelegramUser,
} from "../scopes";
import gravatar from "gravatar-url";
import { hash } from "../utils/hash";
// eslint-disable-next-line import/no-cycle
import { Favorite } from "./favorite";
// eslint-disable-next-line import/no-cycle
import { MumbleLink } from "./mumble-link";
// eslint-disable-next-line import/no-cycle
import { Playlist } from "./playlist";
// eslint-disable-next-line import/no-cycle
import { Sound } from "./sound";
// eslint-disable-next-line import/no-cycle
import { SoundRating } from "./sound-rating";
// eslint-disable-next-line import/no-cycle
import { Token } from "./token";
// eslint-disable-next-line import/no-cycle
import { TelegramUser } from "./telegram-user";

/**
 * A user from the database.
 */
@Entity()
export class User {
    @PrimaryGeneratedColumn("uuid")
    @scope(
        listRatings,
        rateSound,
        world,
        createMumbleLink,
        live,
        listPlaylists,
        statistics,
        createFavorite,
        linkTelegramUser,
    )
    @(is().validate(uuid))
    public id?: string;

    /**
     * The username of this user.
     */
    @Column("varchar", { length: 100 })
    @(is()
        .validate(length(3, 100), only(signup, required))
        .validateCtx((ctx) => only(signup, (value) => ctx.validation.nameAvailable(value)))
        .validateCtx((ctx) => only(updateUser, (value) => ctx.validation.nameAvailable(value))))
    @scope(world, signup, updateUser)
    public name?: string;

    /**
     * The password of the user.
     */
    @Column("varchar", { length: 200 })
    @transform(hash)
    @(is().validate(length(8, 255)))
    @scope(login, updateUser)
    public password?: string;

    @Column("varchar", { length: 200 })
    @(is()
        .validate(length(8, 200), only(login, required))
        .validateCtx((ctx) => only(signup, (value) => ctx.validation.emailAvailable(value)))
        .validateCtx((ctx) => only(updateUser, (value) => ctx.validation.emailAvailable(value))))
    @scope(owner, login, updateUser)
    public email?: string;

    @Column("integer", { default: 0 })
    public score?: number;

    @OneToMany(() => Sound, (sound) => sound.user)
    @is()
    @scope(world)
    @specify(() => Sound)
    public sounds?: Sound[];

    @OneToMany(() => Sound, (sound) => sound.creator)
    @is()
    @scope(world)
    @specify(() => Sound)
    public reported?: Sound[];

    @OneToMany(() => Token, (token) => token.user)
    @is()
    @specify(() => Token)
    @scope(owner)
    public tokens?: Token[];

    @OneToMany(() => MumbleLink, (mumbleLink) => mumbleLink.user)
    @is()
    @specify(() => MumbleLink)
    public mumbleLinks?: MumbleLink[];

    @OneToMany(() => Playlist, (playlist) => playlist.creator)
    public playlists?: Playlist[];

    @precompute
    @scope(world)
    public get avatarUrl(): string {
        if (!this.email) {
            return;
        }
        return gravatar(this.email, { size: 200, default: "identicon" });
    }

    @Column("boolean", { default: false })
    @is()
    @scope(world, updateUser)
    public enabled?: boolean;

    @Column("boolean", { default: false })
    @is()
    @scope(world, updateUser)
    public admin?: boolean;

    @OneToMany(() => SoundRating, (soundRating) => soundRating.user)
    @is()
    @specify(() => SoundRating)
    public soundRatings?: SoundRating[];

    @OneToMany(() => Favorite, (favorite) => favorite.user)
    @is()
    @specify(() => Favorite)
    public favorites?: Favorite[];

    @OneToMany(() => TelegramUser, (telegramUser) => telegramUser.user)
    @is()
    @specify(() => TelegramUser)
    public telegramUsers?: TelegramUser[];
}
