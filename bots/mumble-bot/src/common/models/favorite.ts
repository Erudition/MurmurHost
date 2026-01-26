import { PrimaryGeneratedColumn, Entity, ManyToOne } from "typeorm";
import { is, scope, specify, uuid } from "hyrest";
import { world, createFavorite } from "../scopes";
// eslint-disable-next-line import/no-cycle
import { Sound } from "./sound";
// eslint-disable-next-line import/no-cycle
import { User } from "./user";

@Entity()
export class Favorite {
    @PrimaryGeneratedColumn("uuid")
    @scope(world, createFavorite)
    @(is().validate(uuid))
    public id?: string;

    @ManyToOne(() => Sound, (sound) => sound.favorites)
    @scope(world, createFavorite)
    @is()
    @specify(() => Sound)
    public sound?: Sound;

    @ManyToOne(() => User, (user) => user.favorites)
    @scope(world, createFavorite)
    @is()
    @specify(() => User)
    public user?: User;
}
