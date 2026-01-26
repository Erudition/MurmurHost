import { error, info, verbose } from "winston";
import { inject, component } from "tsdi";
import TelegramBot, { InlineQuery, InlineQueryResultVoice } from "node-telegram-bot-api";
import { Sounds } from "../../common/controllers/sounds";
import { Sound } from "../../common/models/sound";
import { ServerConfig } from "../../config/server-config";
import { TelegramCommand } from "./telegram-command";
import { TelegramBotCommandUsers } from "./command-users";
import { TelegramBotCommandLink } from "./command-link";
import { TelegramBotCommandLinkStatus } from "./command-link-status";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { TelegramBotCommandFavorites } from "./command-favorites";
import { TelegramBotCommandStalk } from "./command-stalk";

@component
export class Telegram {
    @inject private readonly telegramUsers!: TelegramUsers;
    @inject private readonly config!: ServerConfig;
    @inject private readonly sounds!: Sounds;

    private telegramBot?: TelegramBot;

    private commands: TelegramCommand[] = [];

    private mp3UrlOfSound({ id, description }: Sound): string {
        const fileName = description.toLowerCase().replace(/[^a-z0-9]/gi, "-");
        return `${this.config.publicApiUrl}/sound/${id}/download/${fileName}.ogg`;
    }

    /**
     * Register a new command. This will memorize the command, register the handler and refresh telegram's command list.
     */
    public addCommand(command: TelegramCommand): void {
        this.commands.push(command);
        verbose(`Telegram command "/${command.command}" registered.`);
        this.telegramBot.onText(new RegExp(`^/${command.command}(?:@.*?)?$`), command.onMessage);
        this.telegramBot.setMyCommands(this.commands.map(({ command, description }) => ({ command, description })));
    }

    public async connect(): Promise<void> {
        const { telegramBotToken, publicApiUrl } = this.config;
        if (!telegramBotToken) {
            info("Skipping connection to Telegram bot.");
            return;
        }
        if (!publicApiUrl) {
            error("Must specify --public-api-url when specifying --telegram-bot-token.");
            info("Skipping connection to Telegram bot.");
            return;
        }

        info("Connecting to Telegram.");
        this.telegramBot = new TelegramBot(telegramBotToken, { polling: true });

        // Sound inline query.
        this.telegramBot.on("inline_query", async (query: InlineQuery) => {
            const linkedUsers = await this.telegramUsers.getTelegramUsers(query.from.username);
            if (!linkedUsers.some((linkedUser) => Boolean(linkedUser.user?.id))) {
                this.telegramBot.sendMessage(
                    query.from.id,
                    `I don't know you, @${query.from.username}. Use /link to link to me an complete the process in the webinterface.`,
                );

                this.telegramBot.answerInlineQuery(query.id, [], { cache_time: 0 });
                return;
            }

            // Infinite search.
            const offset = query.offset ? Number(query.offset) : 0;

            // Create results array from sounds in current pagination range.
            const { sounds } = await this.sounds.querySounds({ search: query.query, limit: 5, offset });
            const results: InlineQueryResultVoice[] = sounds.map((sound) => ({
                type: "voice",
                id: sound.id,
                voice_url: this.mp3UrlOfSound(sound),
                voice_duration: Math.round(sound.duration),
                title: sound.description,
                caption: sound.description,
            }));

            // Send answer.
            this.telegramBot.answerInlineQuery(query.id, results, { cache_time: 60, next_offset: `${offset + 5}` });

            // Convenient log message for debugging purposes.
            const infoText = results
                .reduce(
                    (result, { title, voice_url, voice_duration }) =>
                        `${result}  - ${title} ${voice_duration}s ${voice_url}\n`,
                    "",
                )
                .trim();
            verbose(`Anwering Telegram inline query "${query.query}" at offset ${offset}:\n${infoText}`);
        });

        // Error handling.
        this.telegramBot.on("error", (err) => error(`Telegram bot: ${err.message}`, err));
        this.telegramBot.on("polling_error", (err) => error(`Telegram bot polling: ${err.message}`, err));

        this.addCommand(new TelegramBotCommandUsers(this.telegramBot));
        this.addCommand(new TelegramBotCommandLink(this.telegramBot));
        this.addCommand(new TelegramBotCommandLinkStatus(this.telegramBot));
        this.addCommand(new TelegramBotCommandFavorites(this.telegramBot));
        this.addCommand(new TelegramBotCommandStalk(this.telegramBot));
    }
}
