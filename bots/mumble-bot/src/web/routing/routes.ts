import { PageCached } from "../pages/cached/cached";
import { PageDashboard } from "../pages/dashboard/dashboard";
import { PageFavorites } from "../pages/favorites/favorites";
import { PageFork } from "../pages/fork/fork";
import { PageLogin } from "../pages/login/login";
import { PagePlaylists } from "../pages/playlists/playlists";
import { PageSettings } from "../pages/settings/settings";
import { PageSignup } from "../pages/signup/signup";
import { PageSound } from "../pages/sound/sound";
import { PageSounds } from "../pages/sounds/sounds";
import { PageUpload } from "../pages/upload/upload";
import { PageUser } from "../pages/user/user";
import { PageUsers } from "../pages/users/users";
import { PageYoutube } from "../pages/youtube/youtube";
import {
    routeLogin,
    routeDashboard,
    routeSignup,
    routeUser,
    routeSettings,
    routeUsers,
    routeSounds,
    routeCached,
    routePlaylists,
    routeUpload,
    routeYoutube,
    routeSound,
    routeFork,
    routeFavorites,
} from "./routing";

export const routes = [
    {
        component: PageLogin,
        route: routeLogin,
    },
    {
        component: PageDashboard,
        route: routeDashboard,
    },
    {
        component: PageSignup,
        route: routeSignup,
    },
    {
        component: PageUser,
        route: routeUser,
    },
    {
        component: PageSettings,
        route: routeSettings,
    },
    {
        component: PageUsers,
        route: routeUsers,
    },
    {
        component: PageSounds,
        route: routeSounds,
    },
    {
        component: PageCached,
        route: routeCached,
    },
    {
        component: PagePlaylists,
        route: routePlaylists,
    },
    {
        component: PageUpload,
        route: routeUpload,
    },
    {
        component: PageYoutube,
        route: routeYoutube,
    },
    {
        component: PageFork,
        route: routeFork,
    },
    {
        component: PageSound,
        route: routeSound,
    },
    {
        component: PageFavorites,
        route: routeFavorites,
    },
];
