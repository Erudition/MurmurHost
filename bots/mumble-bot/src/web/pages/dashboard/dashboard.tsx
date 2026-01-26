import * as React from "react";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { Grid, Card, Header, Icon } from "semantic-ui-react";
import { ChannelTree } from "../../components/channel-tree/channel-tree";
import { ChartOverview } from "../../components/chart-overview/chart-overview";
import { ChartRecordingsPerUser } from "../../components/chart-recordings-per-user/chart-recordings-per-user";
import { ChartSoundsPerMonth } from "../../components/chart-sounds-per-month/chart-sounds-per-month";
import { ChartSoundsPerSource } from "../../components/chart-sounds-per-source/chart-sounds-per-source";
import { Content } from "../../components/content/content";
import { Redirect } from "react-router-dom";
import { routeLogin } from "../../routing/routing";
import { LoginStore } from "../../store/login";

@observer
@external
export class PageDashboard extends React.Component {
    @inject private readonly login!: LoginStore;

    public render(): JSX.Element {
        if (!this.login.loggedIn) {
            return <Redirect to={routeLogin.path()} />;
        }
        return (
            <Content>
                <Grid>
                    <Grid.Row>
                        <Header as="h2" icon textAlign="center">
                            <Icon name="dashboard" />
                            <Header.Content>Dashboard</Header.Content>
                            <Header.Subheader>Get a quick grasp about what's going on.</Header.Subheader>
                        </Header>
                    </Grid.Row>
                    <Grid.Row>
                        <Grid.Column mobile={16} computer={10} tablet={10}>
                            <ChartOverview />
                            <ChartSoundsPerMonth />
                            <ChartSoundsPerSource />
                            <ChartRecordingsPerUser />
                        </Grid.Column>
                        <Grid.Column mobile={16} computer={6} tablet={6}>
                            <Card fluid>
                                <Card.Content>Server Tree</Card.Content>
                                <Card.Content>
                                    <ChannelTree />
                                </Card.Content>
                            </Card>
                        </Grid.Column>
                    </Grid.Row>
                </Grid>
            </Content>
        );
    }
}
