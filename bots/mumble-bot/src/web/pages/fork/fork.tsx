import * as React from "react";
import { Redirect } from "react-router-dom";
import { observable, computed } from "mobx";
import { observer } from "mobx-react";
import { external, inject } from "tsdi";
import { Dimmer, Loader, Grid } from "semantic-ui-react";
import { Sound } from "../../../common/models/sound";
import { Content } from "../../components/content/content";
import { Forker } from "../../components/forker/forker";
import { SoundsStore } from "../../store/sounds";
import { routeLogin } from "../../routing/routing";
import { LoginStore } from "../../store/login";

export interface PageForkProps {
    readonly match: {
        readonly params: {
            readonly id: string;
        };
    };
}

@external
@observer
export class PageFork extends React.Component<PageForkProps> {
    @inject private readonly sounds!: SoundsStore;
    @inject private readonly login!: LoginStore;

    @observable private loading = true;

    public componentWillMount(): void {
        this.load(this.props.match.params.id);
    }

    public componentWillReceiveProps(props: PageForkProps): void {
        this.load(props.match.params.id);
    }

    private async load(id: string): Promise<void> {
        this.loading = true;
        await this.sounds.byId(id);
        this.loading = false;
    }

    @computed private get sound(): Sound {
        return this.sounds.sounds.get(this.props.match.params.id);
    }

    public render(): JSX.Element {
        if (!this.login.loggedIn) {
            return <Redirect to={routeLogin.path()} />;
        }
        if (this.loading) {
            return (
                <Dimmer.Dimmable dimmed={this.loading}>
                    <Dimmer active={this.loading} inverted>
                        <Loader>Loading</Loader>
                    </Dimmer>
                </Dimmer.Dimmable>
            );
        }
        return (
            <Content>
                <Grid>
                    <Grid.Row>
                        <Grid.Column width={16}>
                            <h2>{this.sound.description}</h2>
                        </Grid.Column>
                    </Grid.Row>
                    <Grid.Row>
                        <Grid.Column width={16}>
                            <Forker id={this.sound.id} />
                        </Grid.Column>
                    </Grid.Row>
                </Grid>
            </Content>
        );
    }
}
