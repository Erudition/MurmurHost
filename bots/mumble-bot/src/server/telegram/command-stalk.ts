import { bind } from "decko";
import TelegramBot, { Message } from "node-telegram-bot-api";
import { external, initialize, inject } from "tsdi";
import { CallbackDataType, CallbackQueryData, TelegramCommand } from "./telegram-command";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { error } from "winston";
import { Mumble } from "../mumble";
import { MumbleLinks } from "../../common/controllers/mumble-links";
import { prop, splitEvery, uniqBy } from "ramda";

@external
export class TelegramBotCommandStalk implements TelegramCommand {
    @inject private readonly telegramUsers!: TelegramUsers;
    @inject private readonly mumble!: Mumble;
    @inject private readonly mumbleLinks!: MumbleLinks;

    public readonly command = "stalk";

    public readonly description = "Wait until a specified user does something.";

    private registeredListeners: { mumbleId: number; chatId: number }[] = [];

    constructor(private telegramBot: TelegramBot) {
        this.telegramBot.on("callback_query", async (query) => {
            const data: CallbackQueryData = JSON.parse(query.data);
            if (data[0] != CallbackDataType.STALK) {
                return;
            }
            const mumbleId = data[1];
            const linkedUsers = await this.telegramUsers.getTelegramUsers(query.from.username);
            if (!linkedUsers.some((linkedUser) => Boolean(linkedUser.user?.id))) {
                error(`Received telegram stalk command response from unknown telegram user "${query.from.username}.`);
                return;
            }
            this.telegramBot.sendMessage(query.message.chat.id, "\u{1F648}");
            this.registeredListeners.push({ mumbleId, chatId: query.message.chat.id });
        });
    }

    @initialize protected async initialize(): Promise<void> {
        this.mumble.connection.on("user-update", this.onUserStateChange);
    }

    @bind private onUserStateChange({ user_id, name }: { user_id: number; name: string }): void {
        this.registeredListeners
            .filter(({ mumbleId }) => mumbleId === user_id)
            .forEach(({ chatId }) => this.telegramBot.sendMessage(chatId, `Aha! ${name} did something \u{1F92B}.`));
        this.registeredListeners = this.registeredListeners.filter(({ mumbleId }) => mumbleId !== user_id);
    }

    @bind public async onMessage(msg: Message): Promise<void> {
        const linkedUsers = await this.telegramUsers.getTelegramUsers(msg.from.username);
        if (!linkedUsers.some((linkedUser) => Boolean(linkedUser.user?.id))) {
            this.telegramBot.sendMessage(
                msg.chat.id,
                `I don't know you, @${msg.from.username}. Use /link to link to me an complete the process in the webinterface.`,
            );
            return;
        }
        const users: { name: string; id: number }[] = uniqBy(prop("id"), [
            ...this.mumble.connection
                .users()
                .filter(({ isRegistered }) => isRegistered)
                .map(({ name, id }) => ({ name, id })),
            ...(await this.mumbleLinks.getMumbleLinks()).map(({ mumbleId: id, user: { name } }) => ({ name, id })),
        ]);

        await this.telegramBot.sendMessage(msg.chat.id, `I can stalk these users for you, @${msg.from.username}:`, {
            reply_markup: {
                inline_keyboard: splitEvery(
                    2,
                    users.map(({ name, id }) => ({
                        text: name,
                        callback_data: JSON.stringify([CallbackDataType.STALK, id]),
                    })),
                ),
            },
        });
    }
}
