import * as React from "react";
import classNames from "classnames";
import * as Color from "color";
import { external, inject } from "tsdi";
import { Popup, Form, Image, Icon } from "semantic-ui-react";
import { observer } from "mobx-react";
import { computed, observable, action } from "mobx";
import { bind } from "decko";
import * as css from "./cached-audio-timeline-block.scss";
import { CachedAudio } from "../../../common/models/cached-audio";
import { CachedAudioStore } from "../../store/cached-audio";
import { SoundsStore } from "../../store/sounds";

declare const baseUrl: string;

const amplitudeThreshold = 40.6;

@external
@observer
export class CachedAudioTimelineBlock extends React.Component<{ cachedAudio: CachedAudio }> {
    @inject private readonly cachedAudio!: CachedAudioStore;
    @inject private readonly sounds!: SoundsStore;

    @observable private description = "";
    @observable private isOpen = false;
    @observable private loading = false;
    @observable private paused = true;

    private audio: HTMLAudioElement;

    public componentWillUnmount(): void {
        if (typeof this.audio !== "undefined") {
            this.audio.pause();
            delete this.audio;
        }
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

    @computed private get left(): number {
        const { cachedAudio, props } = this;
        const { selectionStart, selectedRange } = cachedAudio;
        return (props.cachedAudio.date.getTime() - selectionStart.getTime()) / selectedRange;
    }

    @computed private get width(): number {
        return (this.props.cachedAudio.duration * 1000) / this.cachedAudio.selectedRange;
    }

    @bind @action private handleDescriptionChange({ currentTarget }: React.SyntheticInputEvent): void {
        this.description = currentTarget.value;
    }

    @bind @action private async handleSave(): Promise<void> {
        this.loading = true;
        await this.sounds.save(this.props.cachedAudio, this.description);
        this.loading = false;
    }

    @bind @action private handleOpen(): void {
        this.initializeAudio();
        this.isOpen = true;
        this.audio.play();
    }

    @bind @action private handleClose(): void {
        this.isOpen = false;
        this.audio.pause();
    }

    @bind @action private handlePlay(event: React.MouseEvent<HTMLButtonElement>): void {
        this.initializeAudio();
        event.preventDefault();
        if (this.audio.paused) {
            this.audio.currentTime = 0;
            this.audio.play();
            return;
        }
        this.audio.pause();
    }

    @bind @action private async handleDelete(event: React.MouseEvent<HTMLButtonElement>): Promise<void> {
        event.preventDefault();
        this.loading = true;
        await this.cachedAudio.delete(this.props.cachedAudio);
        this.loading = false;
    }

    private get visualizationUrl(): string {
        return `${baseUrl}/cached/${this.props.cachedAudio.id}/visualized`;
    }
    private get audioUrl(): string {
        return `${baseUrl}/cached/${this.props.cachedAudio.id}/download`;
    }

    public render(): JSX.Element {
        const { amplitude, date, duration } = this.props.cachedAudio;
        const { amplitudeTotalRange: totalRange, amplitudeTotalMin: totalMin } = this.cachedAudio;
        const classes = classNames(css.block, "inverted", "violet", {
            [css.open]: this.isOpen,
        });
        const left = `${100 * this.left}%`;
        const width = `${100 * this.width}%`;
        const normalizedAmplitude = totalRange === 0 ? 1 : (amplitude - totalMin) / totalRange;
        const saturation = amplitude < amplitudeThreshold ? 0 : normalizedAmplitude;
        const backgroundColor = Color.hsl(250, 100 * saturation, 77).string();
        return (
            <Popup
                on="click"
                trigger={<div className={classes} style={{ backgroundColor, left, width }} />}
                onOpen={this.handleOpen}
                onClose={this.handleClose}
                hideOnScroll
                wide="very"
                position="top center"
                className={css.popup}
            >
                <Image className={css.image} height={40} src={this.visualizationUrl} />
                <Popup.Content>
                    <Form unstackable onSubmit={this.handleSave} loading={this.loading}>
                        <Form.Group unstackable>
                            <Form.Input
                                label="Description"
                                placeholder={`Recording from ${date.toISOString()}`}
                                value={this.description}
                                onChange={this.handleDescriptionChange}
                                autoFocus
                            />
                            <Form.Button onClick={this.handleDelete} label="Delete" icon="trash" color="red" />
                            <Form.Button
                                onClick={this.handlePlay}
                                label="Play"
                                icon={this.paused ? "play" : "stop"}
                                color="blue"
                            />
                            <Form.Button role="submit" label="Save" icon="checkmark" color="green" />
                        </Form.Group>
                    </Form>
                    <div className={css.info}>
                        <div>
                            <Icon name="time" /> {duration}s
                        </div>
                        <div>
                            <Icon name="calendar" /> {date.toLocaleString()}
                        </div>
                        <div>
                            <Icon name="volume up" /> {amplitude.toFixed(2)}db
                        </div>
                    </div>
                </Popup.Content>
            </Popup>
        );
    }
}
