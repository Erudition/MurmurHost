import { bind } from "decko";
import TelegramBot, { Message } from "node-telegram-bot-api";
import { external, inject } from "tsdi";
import { TelegramCommand } from "./telegram-command";
import { TelegramUsers } from "../../common/controllers/telegram-users";

@external
export class TelegramBotCommandLinkStatus implements TelegramCommand {
    @inject private readonly telegramUsers!: TelegramUsers;

    constructor(private telegramBot: TelegramBot) {}

    public readonly command = "linkstatus";
    public readonly description = "Check whether the current telegram user is linked.";

    @bind public async onMessage(msg: Message): Promise<void> {
        const linkedUsers = await this.telegramUsers.getTelegramUsers(msg.from.username);
        if (linkedUsers.length === 0) {
            this.telegramBot.sendMessage(
                msg.chat.id,
                `There are no link to @${msg.from.username}. Neither fully linked, nor incoming. Send me /${this.command} to initiate a link.`,
            );
            return;
        }
        const [linkedUser] = linkedUsers;
        if (!linkedUser.user?.id) {
            this.telegramBot.sendMessage(
                msg.chat.id,
                `A link to @${msg.from.username} exists, but is not yet linked to any user in the bot. Go to the settings page to complete the link.`,
            );
            return;
        }
        this.telegramBot.sendMessage(
            msg.chat.id,
            `Telegram user @${msg.from.username} is linked to user "${linkedUser.user.name}".`,
        );
    }
}
