import { bind } from "decko";
import TelegramBot, { Message } from "node-telegram-bot-api";
import { external, inject } from "tsdi";
import { TelegramCommand } from "./telegram-command";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { verbose } from "winston";

@external
export class TelegramBotCommandLink implements TelegramCommand {
    @inject private readonly telegramUsers!: TelegramUsers;

    constructor(private telegramBot: TelegramBot) {}

    public readonly command = "link";
    public readonly description = "Greet the bot and enable linking to user on webpage.";

    @bind public async onMessage(msg: Message): Promise<void> {
        verbose(`Telegram user ${msg.from.username} tries to link.`);
        if (await this.telegramUsers.createIncomingTelegramUser({ telegramName: msg.from.username })) {
            this.telegramBot.sendMessage(
                msg.chat.id,
                `Hey, @${msg.from.username}: Incoming link created. You can now link to this telegram user in the web interface.`,
            );
        } else {
            this.telegramBot.sendMessage(
                msg.chat.id,
                `Hey, @${msg.from.username}. I don't want to link with you. Maybe we're already linked?`,
            );
        }
    }
}
