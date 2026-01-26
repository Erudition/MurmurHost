import * as React from "react";
import { observer } from "mobx-react";
import { action, computed, observable } from "mobx";
import { bind } from "decko";
import { external, inject } from "tsdi";
import { Button } from "semantic-ui-react";
import * as css from "./sound-card.scss";
import { Sound } from "../../../common/models/sound";
import { PlaylistsStore } from "../../store/playlists";
import { SoundsStore } from "../../store/sounds";

export interface ButtonsProps {
    sound: Sound;
}

declare const baseUrl: string;

@observer
@external
export class Buttons extends React.Component<ButtonsProps> {
    @inject private readonly sounds!: SoundsStore;
    @inject private readonly playlists!: PlaylistsStore;

    @observable private loading = false;
    @observable private paused = true;

    private audio: HTMLAudioElement;

    private get audioUrl(): string {
        return `${baseUrl}/sound/${this.props.sound.id}/download`;
    }

    public componentWillUnmount(): void {
        if (typeof this.audio !== "undefined") {
            this.audio.pause();
            delete this.audio;
        }
    }

    @computed private get isFavorite(): boolean {
        return this.sounds.isFavorite(this.props.sound.id);
    }

    @bind private initializeAudio(): void {
        if (typeof this.audio !== "undefined") {
            return;
        }
        this.audio = new Audio(this.audioUrl);
        this.audio.addEventListener("pause", () => (this.paused = true));
        this.audio.addEventListener("ended", () => (this.paused = true));
        this.audio.addEventListener("play", () => (this.paused = false));
    }

    @bind @action private async handleDownloadClick(): Promise<void> {
        window.open(this.audioUrl, "Download");
    }

    @bind @action private async handleFavorite(): Promise<void> {
        await this.sounds.toggleFavorite(this.props.sound.id);
    }

    @bind @action private async handlePlayClick(): Promise<void> {
        this.loading = true;
        await this.sounds.play(this.props.sound);
        this.loading = false;
    }

    @bind @action private async handlePreviewClick(): Promise<void> {
        this.initializeAudio();
        if (this.audio.paused) {
            this.audio.currentTime = 0;
            this.audio.play();
            return;
        }
        this.audio.pause();
    }

    @bind @action private handleAddQuickListClick(): void {
        this.playlists.addQuickEntry(this.props.sound);
    }

    public render(): JSX.Element {
        const { used } = this.props.sound;
        return (
            <div className={css.buttonContainer}>
                <Button
                    className={css.button}
                    icon="volume up"
                    label={{ as: "a", basic: true, pointing: "right", content: used }}
                    labelPosition="left"
                    onClick={this.handlePlayClick}
                    loading={this.loading}
                    disabled={this.loading}
                    color="green"
                    size="tiny"
                />
                <Button
                    className={css.button}
                    icon={this.paused ? "headphone" : "stop"}
                    onClick={this.handlePreviewClick}
                    color="blue"
                    size="tiny"
                />
                <Button
                    className={css.button}
                    icon="download"
                    onClick={this.handleDownloadClick}
                    color="blue"
                    size="tiny"
                />
                <Button
                    className={css.button}
                    icon="add"
                    onClick={this.handleAddQuickListClick}
                    color="yellow"
                    size="tiny"
                />
                <Button
                    className={css.button}
                    icon={this.isFavorite ? "heart" : "heart outline"}
                    onClick={this.handleFavorite}
                    color={this.isFavorite ? "red" : undefined}
                    size="tiny"
                />
            </div>
        );
    }
}
