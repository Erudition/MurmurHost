import * as React from "react";
import { Sidebar, Menu, Icon } from "semantic-ui-react";
import { Slider } from "react-semantic-ui-range";
import { observer } from "mobx-react";
import { inject, external } from "tsdi";
import { bind } from "decko";
import { action } from "mobx";
import { routes } from "../../routing/routes";
import { MumbleStatus } from "./mumble-status";
import { Utilities } from "../../../common/controllers/utilities";
import { LiveWebsocket } from "../../store/live-websocket";
import { LoginStore } from "../../store/login";
import { SidebarStore } from "../../store/sidebar";
import { SoundsStore } from "../../store/sounds";
import { BrowserHistory } from "../../factories/history";

@observer
@external
export class AppSidebar extends React.Component {
    @inject private readonly sidebar!: SidebarStore;
    @inject private readonly login!: LoginStore;
    @inject private readonly sounds!: SoundsStore;
    @inject private readonly browserHistory!: BrowserHistory;
    @inject private readonly liveWebsocket!: LiveWebsocket;
    @inject private readonly utilities!: Utilities;

    @bind @action private async handleShutUp(): Promise<void> {
        await this.utilities.shutUp();
    }

    public render(): JSX.Element {
        return (
            <Sidebar
                as={Menu}
                animation="uncover"
                visible={this.sidebar.visible && this.login.loggedIn}
                vertical
                inverted
            >
                {routes.reduce((result, route) => {
                    if (!route.route.navbar) {
                        return result;
                    }
                    const { title, icon, path } = route.route;
                    result.push(
                        <Menu.Item
                            key={title}
                            name={title}
                            content={title}
                            onClick={() => {
                                this.browserHistory.push(path());
                                this.sidebar.visibilityToggled = false;
                            }}
                            icon={icon}
                        />,
                    );
                    return result;
                }, [])}
                <Menu.Item name="shut up" content="Shut up" onClick={this.handleShutUp} icon="alarm mute" />
                <Menu.Item
                    name="logout"
                    content="Logout"
                    onClick={() => {
                        this.login.logout();
                        window.location.href = "/";
                    }}
                    icon="sign out"
                />
                <Menu.Item
                    disabled
                    content={this.liveWebsocket.loading ? "Websocket connecting ..." : "Websocket connected"}
                    icon={this.liveWebsocket.loading ? <Icon loading name="spinner" /> : <Icon name="check" />}
                />
                <MumbleStatus />
                <Menu.Item>
                    <p>Pitch</p>
                    <Slider
                        color="violet"
                        inverted
                        value={this.sounds.pitch}
                        settings={{
                            min: -5000,
                            max: 3000,
                            step: 100,
                            onChange: (value) => (this.sounds.pitch = value),
                        }}
                    />
                </Menu.Item>
                <Menu.Item>
                    <p>Echo</p>
                    <Slider
                        color="violet"
                        inverted
                        value={this.sounds.echo}
                        settings={{
                            min: 0,
                            max: 300,
                            step: 10,
                            onChange: (value) => (this.sounds.echo = value),
                        }}
                    />
                </Menu.Item>
            </Sidebar>
        );
    }
}
