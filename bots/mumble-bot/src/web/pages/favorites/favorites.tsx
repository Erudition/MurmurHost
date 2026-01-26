import * as React from "react";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { computed } from "mobx";
import { Grid, Header, Icon } from "semantic-ui-react";
import * as css from "./favorites.scss";
import { Sound } from "../../../common/models/sound";
import { Content } from "../../components/content/content";
import { SoundCard } from "../../components/sound-card";
import { SoundsStore } from "../../store/sounds";
import { Redirect } from "react-router-dom";
import { LoginStore } from "../../store/login";
import { routeLogin } from "../../routing/routing";

@external
@observer
export class PageFavorites extends React.Component {
    @inject private readonly soundsStore!: SoundsStore;
    @inject private readonly login!: LoginStore;

    @computed private get sounds(): Sound[] {
        return this.soundsStore.favorites
            .map((favorite) => this.soundsStore.sounds.get(favorite.sound.id))
            .filter((sound) => Boolean(sound));
    }

    public render(): JSX.Element {
        if (!this.login.loggedIn) {
            return <Redirect to={routeLogin.path()} />;
        }
        return (
            <Content>
                <Grid>
                    <Grid.Row>
                        <Header as="h2" icon textAlign="center">
                            <Icon name="heart" />
                            <Header.Content>Favorites</Header.Content>
                            <Header.Subheader>Your favorites.</Header.Subheader>
                        </Header>
                    </Grid.Row>
                    <Grid.Row>
                        {this.sounds.map((sound, index) => (
                            <Grid.Column className={css.column} mobile={16} tablet={4} computer={3} key={sound.id}>
                                <SoundCard id={sound.id} zIndex={1000 - index} mini />
                            </Grid.Column>
                        ))}
                    </Grid.Row>
                </Grid>
            </Content>
        );
    }
}
