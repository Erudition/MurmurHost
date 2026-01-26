import { bind } from "decko";
import TelegramBot, { Message } from "node-telegram-bot-api";
import { external, initialize, inject } from "tsdi";
import * as R from "ramda";
import { ChannelTreeChannel, Utilities } from "../../common/controllers/utilities";
import { MumbleUser } from "../../common/models/mumble-user";
import { CallbackDataType, CallbackQueryData, TelegramCommand } from "./telegram-command";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { Mumble } from "../mumble";

const deafIcon = "\u{1F635}";
const muteIcon = "\u{1F910}";
const userIcon = "\u{1F603}";
const channelIcon = "\u{1F3E0}";
const botIcon = "\u{1F916}";

const eastereggIcons = new Map([
    ["svenstaro", "\u{1F914}"],
    ["moerrrlin@zoidberg", "\u{1F92A}"],
    ["libSascha.out", "\u{1F620}"],
]);

@external
export class TelegramBotCommandUsers implements TelegramCommand {
    @inject private readonly utilities!: Utilities;
    @inject private readonly telegramUsers!: TelegramUsers;
    @inject private readonly mumble!: Mumble;

    private registeredListeners: { chatId: number }[] = [];
    private lastString: string;

    constructor(private telegramBot: TelegramBot) {
        this.telegramBot.on("callback_query", async (query) => {
            const data: CallbackQueryData = JSON.parse(query.data);
            if (data[0] != CallbackDataType.USERS) {
                return;
            }
            this.registeredListeners.push({ chatId: query.message.chat.id });
        });
    }

    @initialize protected async initialize(): Promise<void> {
        this.mumble.connection.on("user-update", this.onUserStateChange);
        this.lastString = await this.getCurrentMumbleStateString();
    }

    public readonly command = "users";

    public readonly description = "Lists all connected users per room";

    private readonly indent = (lines: string[]): string[] => lines.map((line) => "        " + line);

    private readonly selectUserIcon = (selfDeaf: boolean, selfMute: boolean, username: string): string =>
        selfDeaf
            ? deafIcon
            : selfMute
            ? muteIcon
            : username === this.mumble.user.name
            ? botIcon
            : eastereggIcons.get(username) ?? userIcon;

    private readonly renderUser = ({ name, selfDeaf, selfMute }: MumbleUser): string[] => [
        `${this.selectUserIcon(selfDeaf, selfMute, name)} *${this.escape(name)}*`,
    ];
    private readonly renderUsers = R.chain(this.renderUser);

    private readonly renderChannel = (recursiveRenderChannels: (channels: ChannelTreeChannel[]) => string[]) => ({
        name,
        children,
        users,
    }: ChannelTreeChannel) =>
        R.unnest([
            [`${channelIcon} ${this.escape(name)}`],
            this.indent(this.renderUsers(users)),
            this.indent(recursiveRenderChannels(children.filter((child) => !this.isEmpty(child)))),
        ]);

    private readonly renderChannels = R.chain((channel: ChannelTreeChannel) =>
        this.renderChannel(this.renderChannels)(channel),
    );

    private readonly escape = (input: string): string =>
        input.replace(/(\[[^\][]*]\(http[^()]*\))|[-.+?^$[\](){}\\]/gi, (x, y) => (y ? y : "\\" + x));

    private readonly isEmpty = (channel: ChannelTreeChannel): boolean =>
        channel.users.length === 0 && channel.children.every(this.isEmpty);

    private async getCurrentMumbleStateString(): Promise<string> {
        const channelTree = await this.utilities.channelTree();
        const displayChannel = R.pipe(this.renderChannel(this.renderChannels), R.join("\n"));
        return displayChannel(channelTree);
    }

    private async sendUsersMessage(target: number): Promise<void> {
        await this.telegramBot.sendMessage(target, await this.getCurrentMumbleStateString(), {
            parse_mode: "MarkdownV2",
            reply_markup: {
                inline_keyboard: [
                    [{ text: "Observe \u{1F9D0}", callback_data: JSON.stringify([CallbackDataType.USERS]) }],
                ],
            },
        });
    }

    @bind private async onUserStateChange(): Promise<void> {
        const currentString = await this.getCurrentMumbleStateString();
        if (this.lastString === currentString) {
            return;
        }
        this.lastString = currentString;
        this.registeredListeners.forEach(({ chatId }) => {
            this.sendUsersMessage(chatId);
        });
        this.registeredListeners = [];
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
        this.sendUsersMessage(msg.chat.id);
    }
}
