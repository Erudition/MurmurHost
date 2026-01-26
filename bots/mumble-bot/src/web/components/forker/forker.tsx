import * as React from "react";
import classNames from "classnames";
import { bind } from "decko";
import { observer } from "mobx-react";
import { computed, observable, action } from "mobx";
import { external, inject } from "tsdi";
import { Dimmer, Loader, Form, Table, Icon } from "semantic-ui-react";
import { routeSound } from "../../routing/routing";
import * as css from "./forker.scss";
import { Sound } from "../../../common/models/sound";
import { SoundsStore } from "../../store/sounds";
import { Brush } from "../brush/brush";
import { BrowserHistory } from "../../factories/history";

declare const baseUrl: string;

@observer
@external
export class Forker extends React.Component<{ id: string }> {
    @inject private readonly sounds!: SoundsStore;
    @inject private readonly browserHistory!: BrowserHistory;

    @observable private selectionStart: number;
    @observable private selectionEnd: number;
    @observable private currentTime: number;
    @observable private loading = true;
    @observable private overwrite = false;
    @observable private description: string;

    private audioContext: AudioContext;
    private nodeSource: AudioBufferSourceNode;
    private nodeSlider: ScriptProcessorNode;
    private audioBuffer: AudioBuffer;

    private get audioUrl(): string {
        return `${baseUrl}/sound/${this.sound.id}/download`;
    }

    private brushing = false;
    private originX: number;
    private container: HTMLDivElement;

    public async componentDidMount(): Promise<void> {
        await this.sounds.byId(this.props.id);
        this.description = this.sound.description;
        this.audioContext = new AudioContext();
        const response = await fetch(this.audioUrl);
        this.audioBuffer = await this.audioContext.decodeAudioData(await response.arrayBuffer());
        this.nodeSlider = this.audioContext.createScriptProcessor(
            1024,
            this.audioBuffer.numberOfChannels,
            this.audioBuffer.numberOfChannels,
        );
        this.nodeSlider.addEventListener("audioprocess", (event: AudioProcessingEvent) => {
            for (let channel = 0; channel < this.nodeSlider.channelCount; ++channel) {
                const inputBuffer = event.inputBuffer.getChannelData(channel);
                const outputBuffer = event.outputBuffer.getChannelData(channel);
                for (let index = 0; index < inputBuffer.length; ++index) {
                    outputBuffer[index] = inputBuffer[index];
                }
            }
            this.currentTime += event.inputBuffer.duration;
        });

        this.loading = false;
        window.addEventListener("mousemove", this.handleMouseMove);
        window.addEventListener("mouseup", this.handleMouseUp);
    }

    public componentWillUnmount(): void {
        window.removeEventListener("mousemove", this.handleMouseMove);
        window.removeEventListener("mouseup", this.handleMouseUp);
    }

    @computed private get brushLeft(): number {
        return this.selectionStart / this.sound.duration;
    }

    @computed private get brushRight(): number {
        return this.selectionEnd / this.sound.duration;
    }

    @computed private get sound(): Sound {
        return this.sounds.sounds.get(this.props.id);
    }

    @computed private get selectionDefined(): boolean {
        return typeof this.selectionStart !== "undefined" && typeof this.selectionEnd !== "undefined";
    }

    @computed private get playing(): boolean {
        return typeof this.currentTime === "number" && !isNaN(this.currentTime);
    }

    @bind private refContainer(div: HTMLDivElement): void {
        this.container = div;
    }

    @bind private handleMouseDown(event: React.MouseEvent<HTMLDivElement>): void {
        const rect = this.container.getBoundingClientRect();
        this.originX = (event.pageX - rect.left) / rect.width;
        this.brushing = true;
        event.stopPropagation();
        event.preventDefault();
    }

    @bind private handleMouseMove(event: MouseEvent): void {
        if (!this.container || !this.brushing) {
            return;
        }
        const rect = this.container.getBoundingClientRect();
        const x = (event.pageX - rect.left) / rect.width;
        this.selectionStart = Math.max(0, Math.min(x, this.originX) * this.sound.duration);
        this.selectionEnd = Math.min(this.sound.duration, Math.max(x, this.originX) * this.sound.duration);
        event.stopPropagation();
        event.preventDefault();
    }

    @bind private handleMouseUp(): void {
        this.brushing = false;
        this.originX = undefined;
    }

    @bind private handleBrushChange(left: number, right: number): void {
        this.selectionStart = Math.max(0, this.sound.duration * left);
        this.selectionEnd = Math.min(this.sound.duration, this.sound.duration * right);
    }

    @bind private handlePlay(event: React.SyntheticEvent<HTMLButtonElement>): void {
        event.stopPropagation();
        event.preventDefault();
        if (this.playing) {
            this.nodeSource.stop();
            this.cleanupAfterPlaybackStopped();
            return;
        }
        const start = this.selectionStart;
        const duration = this.selectionEnd - this.selectionStart;
        this.currentTime = start;
        this.nodeSource = this.audioContext.createBufferSource();
        this.nodeSource.buffer = this.audioBuffer;
        this.nodeSource.connect(this.nodeSlider);
        this.nodeSource.addEventListener("ended", this.cleanupAfterPlaybackStopped);
        this.nodeSlider.connect(this.audioContext.destination);
        this.nodeSource.start(0, start, duration);
    }

    @bind private cleanupAfterPlaybackStopped(): void {
        this.nodeSource.disconnect();
        this.nodeSlider.disconnect();
        this.currentTime = undefined;
    }

    @bind @action private async handleSave(event: React.SyntheticEvent<HTMLFormElement>): Promise<void> {
        event.preventDefault();
        this.loading = true;
        const sound = await this.sounds.fork(
            this.sound,
            this.overwrite,
            this.description,
            this.selectionStart,
            this.selectionEnd,
        );
        this.browserHistory.push(routeSound.path(sound.id));
    }

    @bind @action private handleOverwrite(): void {
        this.overwrite = !this.overwrite;
    }

    @bind @action private handleDescription({ currentTarget }: React.SyntheticInputEvent): void {
        this.description = currentTarget.value;
    }

    private get visualizationUrl(): string {
        return `${baseUrl}/sound/${this.sound.id}/visualized`;
    }

    public render(): JSX.Element {
        const { visualizationUrl } = this;
        const classes = classNames("ui", "card", "fluid", css.container);
        return (
            <>
                <Dimmer.Dimmable dimmed={this.loading}>
                    <Dimmer active={this.loading} inverted>
                        <Loader />
                    </Dimmer>
                    <h3>Select Range</h3>
                    <div
                        style={{ backgroundImage: `url(${visualizationUrl})` }}
                        className={classes}
                        onMouseDown={this.handleMouseDown}
                        ref={this.refContainer}
                    >
                        <div />
                        {this.selectionDefined && (
                            <Brush left={this.brushLeft} right={this.brushRight} onChange={this.handleBrushChange} />
                        )}
                        {this.playing && (
                            <div
                                className={css.currentTime}
                                style={{ left: `${(100 * this.currentTime) / this.sound.duration}%` }}
                            />
                        )}
                        <div />
                    </div>
                    <h3>Meta</h3>
                    <Table>
                        <Table.Row>
                            <Table.Cell>
                                <Icon name="time" /> Original Duration
                            </Table.Cell>
                            <Table.Cell>{this.sound.duration.toFixed(2)}s</Table.Cell>
                        </Table.Row>
                        {this.selectionDefined && (
                            <>
                                <Table.Row>
                                    <Table.Cell>
                                        <Icon name="hourglass start" /> Start
                                    </Table.Cell>
                                    <Table.Cell>{this.selectionStart.toFixed(2)}s</Table.Cell>
                                </Table.Row>
                                <Table.Row>
                                    <Table.Cell>
                                        <Icon name="hourglass end" /> End
                                    </Table.Cell>
                                    <Table.Cell>{this.selectionEnd.toFixed(2)}s</Table.Cell>
                                </Table.Row>
                                <Table.Row>
                                    <Table.Cell>
                                        <Icon name="time" /> New Duration
                                    </Table.Cell>
                                    <Table.Cell>{(this.selectionEnd - this.selectionStart).toFixed(2)}s</Table.Cell>
                                </Table.Row>
                            </>
                        )}
                    </Table>
                    <h3>Save</h3>
                    <Form onSubmit={this.handleSave}>
                        <Form.Checkbox
                            label="Overwrite the existing sound with this one."
                            checked={this.overwrite}
                            onChange={this.handleOverwrite}
                        />
                        <Form.Input icon="file text" value={this.description} onChange={this.handleDescription} />
                        <Form.Group>
                            <Form.Button
                                icon={this.playing ? "stop" : "headphone"}
                                content="Play"
                                color="blue"
                                onClick={this.handlePlay}
                                disabled={!this.selectionDefined}
                            />
                            <Form.Button
                                icon="save"
                                color="green"
                                content="Save"
                                role="submit"
                                disabled={!this.selectionDefined}
                            />
                        </Form.Group>
                    </Form>
                </Dimmer.Dimmable>
            </>
        );
    }
}
