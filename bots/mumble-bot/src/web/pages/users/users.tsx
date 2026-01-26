import * as React from "react";
import { Redirect } from "react-router-dom";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { Grid, Header, Icon } from "semantic-ui-react";
import { Content } from "../../components/content/content";
import { UserList } from "../../components/user-list/user-list";
import { LoginStore } from "../../store/login";
import { routeLogin } from "../../routing/routing";

@observer
@external
export class PageUsers extends React.Component {
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
                                <Icon name="group" />
                                <Header.Content>Users</Header.Content>
                                <Header.Subheader>View a list of all known users.</Header.Subheader>
                            </Header>
                        </Grid.Column>
                    </Grid.Row>
                    <Grid.Row>
                        <Grid.Column>
                            <h3>Users</h3>
                            <div>
                                <UserList />
                            </div>
                        </Grid.Column>
                    </Grid.Row>
                </Grid>
            </Content>
        );
    }
}
