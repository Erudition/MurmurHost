import { Sound } from "./sound";
import { User } from "./user";
import { Tag } from "./tag";
import { SoundTagRelation } from "./sound-tag-relation";
import { Playlist } from "./playlist";
import { PlaylistEntry } from "./playlist-entry";
import { MumbleLink } from "./mumble-link";
import { Token } from "./token";
import { SoundRating } from "./sound-rating";
import { Favorite } from "./favorite";
import { TelegramUser } from "./telegram-user";

export const allDatabaseModels = [
    User,
    Tag,
    SoundTagRelation,
    Sound,
    Playlist,
    PlaylistEntry,
    MumbleLink,
    Token,
    SoundRating,
    Favorite,
    TelegramUser,
];
