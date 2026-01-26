import { PrimaryGeneratedColumn, Entity, ManyToOne } from "typeorm";
import { is, scope, specify, uuid } from "hyrest";
import { world, createSound } from "../scopes";
// eslint-disable-next-line import/no-cycle
import { Sound } from "./sound";
// eslint-disable-next-line import/no-cycle
import { Tag } from "./tag";

@Entity()
export class SoundTagRelation {
    @PrimaryGeneratedColumn("uuid")
    @scope(world)
    @(is().validate(uuid))
    public id?: string;

    @ManyToOne(() => Sound, (sound) => sound.soundTagRelations)
    @is()
    @scope(world)
    @specify(() => Sound)
    public sound?: Sound;

    @ManyToOne(() => Tag, (tag) => tag.soundTagRelations)
    @is()
    @scope(world, createSound)
    @specify(() => Tag)
    public tag?: Tag;
}
