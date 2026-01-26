import { context, body, controller, route, ok, created } from "hyrest";
import { component, inject } from "tsdi";
import { verbose } from "winston";

import { createTag, world } from "../scopes";
import { Context } from "../context";
import { Database } from "../../server/database";
import { Tag } from "../models/tag";

@controller
@component
export class Tags {
    @inject private readonly db!: Database;

    @(route("GET", "/tags").dump(Tag, world))
    public async listTags(): Promise<Tag[]> {
        const tags = await this.db
            .getRepository(Tag)
            .createQueryBuilder("tag")
            .leftJoinAndSelect("tag.soundTagRelations", "soundTagRelation")
            .leftJoin("soundTagRelation.sound", "sound")
            .addSelect("sound.id")
            .getMany();
        return ok(tags);
    }

    @(route("POST", "/tags").dump(Tag, world))
    public async createTag(@body(createTag) tag: Tag, @context ctx?: Context): Promise<Tag> {
        const newTag = await this.db.getRepository(Tag).save(tag);
        const currentUser = await ctx.currentUser();
        verbose(`${currentUser.name} added new tag: "${tag.name}"`);
        return created(newTag);
    }
}
