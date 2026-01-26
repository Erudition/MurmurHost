import { context, body, controller, route, is, ok, created, forbidden, param, notFound, conflict } from "hyrest";
import { verbose } from "winston";
import { component, inject } from "tsdi";
import { createFavorite, world } from "../scopes";
import { Context } from "../context";
import { Database } from "../../server/database";
import { Favorite } from "../models/favorite";

export interface Settings {
    [key: string]: string;
}

@controller
@component
export class Favorites {
    @inject private readonly db!: Database;

    @route("DELETE", "/favorite/:id")
    public async deleteFavorite(@param("id") id: string, @context ctx?: Context): Promise<void> {
        const currentUser = await ctx.currentUser();
        const favorite = await this.db.getRepository(Favorite).findOne({
            where: { id },
            relations: ["user"],
        });
        if (!favorite) {
            return notFound<void>(`No favorite with id "${id}" found.`);
        }
        if (favorite.user.id !== currentUser.id) {
            return forbidden<void>("Can't delete favorite of a foreign user.");
        }
        await this.db.getRepository(Favorite).delete({ id });
        return ok();
    }

    /**
     * Create a new linkage between a database user and a user in the mumble server.
     *
     * @param mumbleLink The the `mumbleId` and `user.id` properties of `Favorite`.
     *
     * @return The created `Favorite`.
     */
    @(route("POST", "/favorite").dump(Favorite, world))
    public async createFavorite(
        @body(createFavorite) @is() favorite: Favorite,
        @context ctx?: Context,
    ): Promise<Favorite> {
        const currentUser = await ctx.currentUser();
        if (favorite.user.id !== currentUser.id) {
            return forbidden<Favorite>("Can't create favorite for a foreign user.");
        }
        const existingLink = await this.db.getRepository(Favorite).findOne({
            where: { user: favorite.user.id, sound: favorite.sound.id },
        });
        if (existingLink) {
            return conflict<Favorite>(
                `User with id "${favorite.user.id}" already has favorite "${favorite.sound.id}".`,
            );
        }
        verbose(`User ${currentUser.id} favorited sound with id "${favorite.sound.id}".`);
        await this.db.getRepository(Favorite).save(favorite);
        return created(favorite);
    }

    /**
     * Returns the list of all mumble links in the database.
     *
     * @return All `Favorite`s.
     */
    @(route("GET", "/favorite/:userId").dump(Favorite, world))
    public async getFavorites(@param("userId") userId: string): Promise<Favorite[]> {
        return ok(
            await this.db.getRepository(Favorite).find({ relations: ["user", "sound"], where: { user: userId } }),
        );
    }
}
