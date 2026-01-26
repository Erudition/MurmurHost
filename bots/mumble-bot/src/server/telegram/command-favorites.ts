import { bind } from "decko";
import TelegramBot, { Message } from "node-telegram-bot-api";
import { external, inject } from "tsdi";
import { CallbackDataType, CallbackQueryData, TelegramCommand } from "./telegram-command";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { Favorites } from "../../common/controllers/favorites";
import { Queue } from "../../common/controllers/queue";
import { Sounds } from "../../common/controllers/sounds";
import { error, verbose } from "winston";
import { QueueItem } from "../../common/models/queue-item";
import { Context } from "../../common/context";

@external
export class TelegramBotCommandFavorites implements TelegramCommand {
    @inject private readonly telegramUsers!: TelegramUsers;
    @inject private readonly favorites!: Favorites;
    @inject private readonly queue!: Queue;
    @inject private readonly sounds!: Sounds;

    public readonly command = "favorites";

    public readonly description = "List all favorite sounds as buttons.";

    constructor(private telegramBot: TelegramBot) {
        this.telegramBot.on("callback_query", async (query) => {
            const data: CallbackQueryData = JSON.parse(query.data);
            if (data[0] != CallbackDataType.FAVORITE) {
                return;
            }
            const id = data[1];
            const linkedUsers = await this.telegramUsers.getTelegramUsers(query.from.username);
            if (!linkedUsers.some((linkedUser) => Boolean(linkedUser.user?.id))) {
                error(
                    `Received telegram favorite command response from unknown telegram user "${query.from.username}.`,
                );
                return;
            }
            const [{ user }] = linkedUsers;
            const sound = await this.sounds.getSound(id);
            if (!sound) {
                error(`Received telegram favorite command response with invalid sounds id "${id}.`);
                return;
            }
            verbose(`Telegram user ${query.from.username} played back sound with id "${sound.id}".`);
            await this.queue.enqueue(Object.assign(new QueueItem(), { type: "sound", sound }), {
                currentUser: async () => user,
            } as Context);
        });
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
        const [{ user }] = linkedUsers;

        const favorites = await this.favorites.getFavorites(user.id);
        await this.telegramBot.sendMessage(
            msg.chat.id,
            `These are your favorite sounds, @${msg.from.username} \u{2764}:`,
            {
                reply_markup: {
                    inline_keyboard: favorites.map(({ sound }) => [
                        {
                            text: sound.description,
                            callback_data: JSON.stringify([CallbackDataType.FAVORITE, sound.id]),
                        },
                    ]),
                },
            },
        );
    }
}
