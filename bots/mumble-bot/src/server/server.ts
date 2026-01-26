import { configure } from "tsdi";
import { Context } from "../common/context";
import { Cached } from "../common/controllers/cached";
import { Favorites } from "../common/controllers/favorites";
import { MumbleLinks } from "../common/controllers/mumble-links";
import { Playlists } from "../common/controllers/playlists";
import { Queue } from "../common/controllers/queue";
import { Sounds } from "../common/controllers/sounds";
import { Statistics } from "../common/controllers/statistics";
import { Tags } from "../common/controllers/tags";
import { TelegramUsers } from "../common/controllers/telegram-users";
import { Tokens } from "../common/controllers/tokens";
import { Users } from "../common/controllers/users";
import { Utilities } from "../common/controllers/utilities";
import { Validation } from "../common/controllers/validation";
import { ServerConfig } from "../config/server-config";
import { VisualizerExecutor } from "../visualizer/executor";
import { LiveWebsocket } from "./api/live-websocket";
import { RestApi } from "./api/rest-api";
import { AudioCache } from "./audio-cache";
import { AudioInput } from "./audio-input/audio-input";
import { VoiceInputUser } from "./audio-input/user";
import { AudioOutput } from "./audio-output";
import { Database } from "./database";
import { Mumble } from "./mumble";
import { TelegramBotCommandFavorites } from "./telegram/command-favorites";
import { TelegramBotCommandLink } from "./telegram/command-link";
import { TelegramBotCommandLinkStatus } from "./telegram/command-link-status";
import { TelegramBotCommandStalk } from "./telegram/command-stalk";
import { TelegramBotCommandUsers } from "./telegram/command-users";
import { Telegram } from "./telegram/telegram";

export class ServerApplication {
    // Externals.
    @configure protected readonly voiceInputUser!: VoiceInputUser;
    @configure protected readonly context!: Context;
    @configure protected readonly liveWebsocket!: LiveWebsocket;
    @configure protected readonly telegramBotCommandUsers!: TelegramBotCommandUsers;
    @configure protected readonly telegramBotCommandLink!: TelegramBotCommandLink;
    @configure protected readonly telegramBotCommandLinkStatus!: TelegramBotCommandLinkStatus;
    @configure protected readonly telegramBotCommandFavorite!: TelegramBotCommandFavorites;
    @configure protected readonly telegramBotCommandStalk!: TelegramBotCommandStalk;

    // Components.
    @configure protected readonly restApi!: RestApi;
    @configure protected readonly database!: Database;
    @configure protected readonly audioCache!: AudioCache;
    @configure protected readonly audioOutput!: AudioOutput;
    @configure protected readonly audioInput!: AudioInput;
    @configure protected readonly visualizer!: VisualizerExecutor;
    @configure protected readonly mumble!: Mumble;
    @configure protected readonly telegram!: Telegram;

    // Controllers.
    @configure protected readonly cached!: Cached;
    @configure protected readonly playlists!: Playlists;
    @configure protected readonly tags!: Tags;
    @configure protected readonly mumbleLinks!: MumbleLinks;
    @configure protected readonly sounds!: Sounds;
    @configure protected readonly tokens!: Tokens;
    @configure protected readonly users!: Users;
    @configure protected readonly utilities!: Utilities;
    @configure protected readonly validation!: Validation;
    @configure protected readonly queue!: Queue;
    @configure protected readonly statistics!: Statistics;
    @configure protected readonly favorites!: Favorites;
    @configure protected readonly telegramUsers!: TelegramUsers;

    @configure
    protected serverConfig(): ServerConfig {
        return this.config;
    }

    constructor(private config: ServerConfig) {}
}
