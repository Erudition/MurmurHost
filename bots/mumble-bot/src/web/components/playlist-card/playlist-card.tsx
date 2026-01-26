import * as React from "react";
import { external, inject } from "tsdi";
import { bind } from "decko";
import { action, observable } from "mobx";
import { Card, Button, List } from "semantic-ui-react";
import { observer } from "mobx-react";
import { PlaylistEntryComponent } from "./playlist-entry";
import { PlaylistDescription } from "./description";
import * as css from "./playlist-card.scss";
import { Playlist } from "../../../common/models/playlist";
import { PlaylistsStore } from "../../store/playlists";

@external
@observer
export class PlaylistCard extends React.Component<{ playlist: Playlist }> {
    @inject private readonly playlists!: PlaylistsStore;

    @observable private loading = false;
    @observable private expanded = false;

    @bind @action private async handlePlayClick(): Promise<void> {
        this.loading = true;
        await this.playlists.play(this.props.playlist);
        this.loading = false;
    }

    @bind @action private handleExpand(): void {
        this.expanded = true;
    }

    @bind private renderEntries(): JSX.Element {
        const { entries } = this.props.playlist;
        if (entries.length <= 3 || this.expanded) {
            return (
                <List>
                    {entries.map((entry) => (
                        <PlaylistEntryComponent key={entry.id} playlistEntry={entry} />
                    ))}
                </List>
            );
        } else {
            const firstThree = entries.slice(0, 3);
            return (
                <>
                    <List>
                        {firstThree.map((entry) => (
                            <PlaylistEntryComponent key={entry.id} playlistEntry={entry} />
                        ))}
                    </List>
                    <div className={css.ellipsis}>
                        <a onClick={this.handleExpand}>{entries.length - 3} Items hidden</a>
                    </div>
                </>
            );
        }
    }

    public render(): JSX.Element {
        const { used } = this.props.playlist;
        return (
            <Card fluid>
                <Card.Content>
                    <Card.Description>
                        <PlaylistDescription playlist={this.props.playlist} />
                    </Card.Description>
                </Card.Content>
                <Card.Content>{this.renderEntries()}</Card.Content>
                <Card.Content extra>
                    <Button
                        content="Play"
                        icon="volume up"
                        label={{ as: "a", basic: true, pointing: "right", content: used }}
                        labelPosition="left"
                        onClick={this.handlePlayClick}
                        loading={this.loading}
                        disabled={this.loading}
                        color="green"
                    />
                </Card.Content>
            </Card>
        );
    }
}
