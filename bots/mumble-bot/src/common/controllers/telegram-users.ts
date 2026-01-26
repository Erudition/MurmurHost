import { verbose } from "winston";
import { component, inject } from "tsdi";
import { Database } from "../../server/database";
import { createTelegramUser, linkTelegramUser, world } from "../scopes";
import { body, conflict, context, controller, created, forbidden, is, notFound, ok, param, query, route } from "hyrest";
import { TelegramUser } from "../models/telegram-user";
import { Context } from "../context";
import { User } from "../models/user";

@controller
@component
export class TelegramUsers {
    @inject private readonly db!: Database;

    @(route("POST", "/telegram-user").dump(TelegramUser, world))
    public async createIncomingTelegramUser(
        @body(createTelegramUser) @is() telegramUser: TelegramUser,
    ): Promise<TelegramUser> {
        const existingUser = await this.db.getRepository(TelegramUser).findOne({
            where: { telegramName: telegramUser.telegramName },
        });
        if (existingUser) {
            return conflict<TelegramUser>(`Telegram user with name "${telegramUser.telegramName}" is already used.`);
        }
        await this.db.getRepository(TelegramUser).save(telegramUser);
        verbose(
            `Created incoming telegram link for telegram user ${telegramUser.telegramName} with id ${telegramUser.id}`,
        );
        return created(telegramUser);
    }

    @(route("POST", "/telegram-user/:id").dump(TelegramUser, world))
    public async updateTelegramUser(
        @param("id") id: string,
        @body(linkTelegramUser) @is() telegramUser: TelegramUser,
        @context ctx?: Context,
    ): Promise<TelegramUser> {
        const currentUser = await ctx.currentUser();
        const existingUser = await this.db.getRepository(TelegramUser).findOne({
            where: { id },
            relations: ["user"],
        });
        if (!existingUser) {
            return notFound<TelegramUser>(`Telegram user with id "${id}" not found.`);
        }
        if (existingUser.user?.id && existingUser.user?.id !== currentUser.id) {
            return forbidden<TelegramUser>(`Can't update linked foreign telegram user.`);
        }
        if (telegramUser.user && telegramUser.user.id && telegramUser.user?.id !== currentUser.id) {
            return forbidden<TelegramUser>(`Can't link telegram user to foreign user.`);
        }
        existingUser.user = telegramUser.user?.id ? ({ id: telegramUser.user.id } as User) : null;
        await this.db.getRepository(TelegramUser).save(existingUser);
        if (telegramUser.user?.id) {
            verbose(`Linked telegram user ${existingUser.telegramName} to user with id "${telegramUser.user.id}".`);
        } else {
            verbose(`Unlinked telegram user ${existingUser.telegramName}.`);
        }
        return ok(
            await this.db.getRepository(TelegramUser).findOne({
                where: { id },
                relations: ["user"],
            }),
        );
    }

    @(route("GET", "/telegram-users").dump(TelegramUser, world))
    public async getTelegramUsers(@query("telegramName") telegramName?: string): Promise<TelegramUser[]> {
        const query = this.db
            .getRepository(TelegramUser)
            .createQueryBuilder("telegram")
            .leftJoinAndSelect("telegram.user", "user");

        if (telegramName) {
            query.where(`telegram."telegramName" = :telegramName`, { telegramName });
        }
        return ok(await query.getMany());
    }
}
