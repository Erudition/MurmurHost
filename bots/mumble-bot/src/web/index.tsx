import * as React from "react";
import * as ReactDOM from "react-dom";
import { configure, TSDI } from "tsdi";
import { Route, Switch, Redirect } from "react-router-dom";
import { Router } from "react-router";
import { configureController, ControllerOptions, Validation } from "hyrest";
import { routeDashboard, routeLogin } from "./routing/routing";
import { routes } from "./routing/routes";
import "./global.scss";
import { allControllers } from "../common/controllers/all-controllers";
import { AppContainer } from "./components/app-container/app-container";
import { ErrorStore } from "./store/errors";
import { LoginStore } from "./store/login";
import { Cached } from "../common/controllers/cached";
import { Favorites } from "../common/controllers/favorites";
import { MumbleLinks } from "../common/controllers/mumble-links";
import { Playlists } from "../common/controllers/playlists";
import { Queue } from "../common/controllers/queue";
import { Sounds } from "../common/controllers/sounds";
import { Statistics } from "../common/controllers/statistics";
import { Tags } from "../common/controllers/tags";
import { Tokens } from "../common/controllers/tokens";
import { Users } from "../common/controllers/users";
import { Utilities } from "../common/controllers/utilities";
import { LiveWebsocket } from "./store/live-websocket";
import { CachedAudioStore } from "./store/cached-audio";
import { MumbleStore } from "./store/mumble";
import { OwnUserStore } from "./store/own-user";
import { PlaylistsStore } from "./store/playlists";
import { QueueStore } from "./store/queue";
import { SidebarStore } from "./store/sidebar";
import { SignupStore } from "./store/signup";
import { SoundsStore } from "./store/sounds";
import { StatisticsStore } from "./store/statistics";
import { TagsStore } from "./store/tags";
import { UsersStore } from "./store/users";
import { BrowserHistory } from "./factories/history";
import { AppBar } from "./components/app-bar/app-bar";
import { MiniQueue } from "./components/app-bar/mini-queue";
import { CachedAudioBlock } from "./components/cached-audio-slider/cached-audio-block";
import { CachedAudioSlider } from "./components/cached-audio-slider/cached-audio-slider";
import { CachedAudioTimeline } from "./components/cached-audio-timeline/cached-audio-timeline";
import { CachedAudioTimelineBlock } from "./components/cached-audio-timeline/cached-audio-timeline-block";
import { ChannelTree } from "./components/channel-tree/channel-tree";
import { TreeUser } from "./components/channel-tree/tree-user";
import { ChartOverview } from "./components/chart-overview/chart-overview";
import { ChartRecordingsPerUser } from "./components/chart-recordings-per-user/chart-recordings-per-user";
import { ChartSoundsPerMonth } from "./components/chart-sounds-per-month/chart-sounds-per-month";
import { ChartSoundsPerSource } from "./components/chart-sounds-per-source/chart-sounds-per-source";
import { Errors } from "./components/errors/errors";
import { Forker } from "./components/forker/forker";
import { MumbleLinker } from "./components/mumble-linker/mumble-linker";
import { PlaylistCard } from "./components/playlist-card/playlist-card";
import { QuickList } from "./components/quick-list/quick-list";
import { MumbleStatus } from "./components/sidebar/mumble-status";
import { SoundCard } from "./components/sound-card";
import { Buttons } from "./components/sound-card/buttons";
import { SoundCardDescription } from "./components/sound-card/description";
import { Meta } from "./components/sound-card/meta";
import { TagLabel } from "./components/tag-label/tag-label";
import { UserList } from "./components/user-list/user-list";
import { PlaylistDescription } from "./components/playlist-card/description";
import { SoundCardTags } from "./components/sound-card/tags";
import { PageCached } from "./pages/cached/cached";
import { PageDashboard } from "./pages/dashboard/dashboard";
import { PageFavorites } from "./pages/favorites/favorites";
import { PageFork } from "./pages/fork/fork";
import { PageLogin } from "./pages/login/login";
import { PagePlaylists } from "./pages/playlists/playlists";
import { PageSettings } from "./pages/settings/settings";
import { PageSignup } from "./pages/signup/signup";
import { PageSound } from "./pages/sound/sound";
import { PageSounds } from "./pages/sounds/sounds";
import { PageUpload } from "./pages/upload/upload";
import { PageUser } from "./pages/user/user";
import { PageUsers } from "./pages/users/users";
import { PageYoutube } from "./pages/youtube/youtube";
import { AppSidebar } from "./components/sidebar/sidebar";
import { ServerConfig } from "../config/server-config";
import { AudioCache } from "../server/audio-cache";
import { AudioOutput } from "../server/audio-output";
import { Database } from "../server/database";
import { Mumble } from "../server/mumble";
import { VisualizerExecutor } from "../visualizer/executor";
import { Context } from "../common/context";
import { AudioInput } from "../server/audio-input/audio-input";
import { PlaylistEntryComponent } from "./components/playlist-card/playlist-entry";
import { TelegramUsers } from "../common/controllers/telegram-users";
import { TelegramUserStore } from "./store/telegram-users";
import { TelegramLinker } from "./components/telegram-linker/telegram-linker";

declare const baseUrl: string;

export class FrontendApplication {
    // Shims.
    @configure protected readonly audioCache!: AudioCache;
    @configure protected readonly audioOutput!: AudioOutput;
    @configure protected readonly audioInput!: AudioInput;
    @configure protected readonly database!: Database;
    @configure protected readonly mumble!: Mumble;
    @configure protected readonly serverConfig!: ServerConfig;
    @configure protected readonly visualizer!: VisualizerExecutor;

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

    // Stores.
    @configure protected readonly cachedAudioStore!: CachedAudioStore;
    @configure protected readonly errorStore!: ErrorStore;
    @configure protected readonly liveWebsockeStore!: LiveWebsocket;
    @configure protected readonly loginStore!: LoginStore;
    @configure protected readonly mumbleStore!: MumbleStore;
    @configure protected readonly ownUserStore!: OwnUserStore;
    @configure protected readonly playlistsStore!: PlaylistsStore;
    @configure protected readonly queueStore!: QueueStore;
    @configure protected readonly sidebarStore!: SidebarStore;
    @configure protected readonly signupStore!: SignupStore;
    @configure protected readonly soundsStore!: SoundsStore;
    @configure protected readonly statisticsStore!: StatisticsStore;
    @configure protected readonly tagsStore!: TagsStore;
    @configure protected readonly usersStore!: UsersStore;
    @configure protected readonly telegramUserStore!: TelegramUserStore;
    @configure protected readonly browserHistory!: BrowserHistory;

    // Components.
    @configure protected readonly appBar!: AppBar;
    @configure protected readonly appSidebar!: AppSidebar;
    @configure protected readonly miniQueue!: MiniQueue;
    @configure protected readonly appContainer!: AppContainer;
    @configure protected readonly cachedAudioBlock!: CachedAudioBlock;
    @configure protected readonly cachedAudioSlider!: CachedAudioSlider;
    @configure protected readonly cachedAudioTimelineBlock!: CachedAudioTimelineBlock;
    @configure protected readonly cachedAudioTimeline!: CachedAudioTimeline;
    @configure protected readonly channelTree!: ChannelTree;
    @configure protected readonly treeUser!: TreeUser;
    @configure protected readonly chartOverview!: ChartOverview;
    @configure protected readonly chartRecordingsPerUser!: ChartRecordingsPerUser;
    @configure protected readonly chartSoundsPerMonth!: ChartSoundsPerMonth;
    @configure protected readonly chartSoundsPerSource!: ChartSoundsPerSource;
    @configure protected readonly errors!: Errors;
    @configure protected readonly forker!: Forker;
    @configure protected readonly mumbleLinker!: MumbleLinker;
    @configure protected readonly soundCardDescription!: SoundCardDescription;
    @configure protected readonly playlistCard!: PlaylistCard;
    @configure protected readonly playlistEntryComponent!: PlaylistEntryComponent;
    @configure protected readonly quickList!: QuickList;
    @configure protected readonly mumbleStatus!: MumbleStatus;
    @configure protected readonly buttons!: Buttons;
    @configure protected readonly playlistDescription!: PlaylistDescription;
    @configure protected readonly meta!: Meta;
    @configure protected readonly soundCard!: SoundCard;
    @configure protected readonly soundCardTags!: SoundCardTags;
    @configure protected readonly tagLabel!: TagLabel;
    @configure protected readonly userList!: UserList;
    @configure protected readonly telegramLinker!: TelegramLinker;

    // Pages.
    @configure protected readonly pageCached!: PageCached;
    @configure protected readonly pageDashboard!: PageDashboard;
    @configure protected readonly pageFavorites!: PageFavorites;
    @configure protected readonly pageFork!: PageFork;
    @configure protected readonly pageLogin!: PageLogin;
    @configure protected readonly pagePlaylists!: PagePlaylists;
    @configure protected readonly pageSettings!: PageSettings;
    @configure protected readonly pageSignup!: PageSignup;
    @configure protected readonly pageSound!: PageSound;
    @configure protected readonly pageSounds!: PageSounds;
    @configure protected readonly pageUpload!: PageUpload;
    @configure protected readonly pageUsers!: PageUsers;
    @configure protected readonly pageUser!: PageUser;
    @configure protected readonly pageYoutube!: PageYoutube;

    // Externals.
    @configure protected readonly context!: Context;
}

const tsdi = new TSDI(new FrontendApplication());

function App(): JSX.Element {
    return (
        <AppContainer>
            <Switch>
                {tsdi.get(LoginStore).loggedIn ? (
                    [
                        <Redirect exact from="/" to={routeDashboard.path()} key="root" />,
                        <Redirect exact from="/login" to={routeDashboard.path()} key="login" />,
                        <Redirect exact from="/signup" to={routeDashboard.path()} key="signup" />,
                    ]
                ) : (
                    <Redirect exact from="/" to={routeLogin.path()} />
                )}
                {routes.map((route, index) => (
                    <Route key={index} path={route.route.pattern} component={route.component} />
                ))}
            </Switch>
        </AppContainer>
    );
}

const errors = tsdi.get(ErrorStore);
const controllerOptions: ControllerOptions = {
    baseUrl,
    errorHandler: (err) => {
        errors.report({
            message: err.answer ? err.answer.message : err.message ? err.message : "Unknown error.",
            fatal: err.statusCode === 401,
        });
        if (err.statusCode === 401) {
            tsdi.get(LoginStore).logout();
        }
    },
    authorizationProvider: (headers: Headers) => {
        const loginStore = tsdi.get(LoginStore);
        if (loginStore.loggedIn) {
            headers.append("authorization", `Bearer ${loginStore.authToken}`);
        }
    },
};

configureController(allControllers, controllerOptions);

ReactDOM.render(
    <div>
        <Router history={tsdi.get(BrowserHistory).history}>
            <App />
        </Router>
    </div>,
    document.getElementById("root"),
);
