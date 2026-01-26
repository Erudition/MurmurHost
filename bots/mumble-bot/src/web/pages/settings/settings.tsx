import * as React from "react";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { Redirect } from "react-router-dom";
import { Grid, Header, Icon } from "semantic-ui-react";
import { Content } from "../../components/content/content";
import { MumbleLinker } from "../../components/mumble-linker/mumble-linker";
import { LoginStore } from "../../store/login";
import { routeLogin } from "../../routing/routing";
import { TelegramLinker } from "../../components/telegram-linker/telegram-linker";

@observer
@external
export class PageSettings extends React.Component {
    @inject private readonly login!: LoginStore;

    public render(): JSX.Element {
        if (!this.login.loggedIn) {
            return <Redirect to={routeLogin.path()} />;
        }
        return (
            <Content>
                <Grid>
                    <Grid.Row>
                        <Grid.Column>
                            <Header as="h2" icon textAlign="center">
                                <Icon name="settings" />
                                <Header.Content>Settings</Header.Content>
                                <Header.Subheader>Change settings and link mumble users.</Header.Subheader>
                            </Header>
                        </Grid.Column>
                    </Grid.Row>
                    <Grid.Row>
                        <Grid.Column>
                            <h3>Link Mumble Users</h3>
                            <div>
                                <MumbleLinker />
                            </div>
                        </Grid.Column>
                    </Grid.Row>
                    <Grid.Row>
                        <Grid.Column>
                            <h3>Link Telegram Users</h3>
                            <div>
                                <TelegramLinker />
                            </div>
                        </Grid.Column>
                    </Grid.Row>
                </Grid>
            </Content>
        );
    }
}
