import * as React from "react";
import classNames from "classnames";
import { bind } from "decko";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { observable, computed } from "mobx";
import { format, addSeconds } from "date-fns";
import { CachedAudioBlock } from "./cached-audio-block";
import * as css from "./cached-audio-slider.scss";
import { CachedAudioStore } from "../../store/cached-audio";
import { Brush } from "../brush/brush";

const tickWidth = 100;

@external
@observer
export class CachedAudioSlider extends React.Component {
    @inject private readonly cachedAudio!: CachedAudioStore;

    @observable private width = 0;

    private brushing = false;
    private originX: number;
    private container: HTMLDivElement;

    public componentDidMount(): void {
        window.addEventListener("mousemove", this.handleMouseMove);
        window.addEventListener("mouseup", this.handleMouseUp);
        window.addEventListener("resize", this.setWidth);
    }

    public componentWillUnmount(): void {
        window.removeEventListener("mousemove", this.handleMouseMove);
        window.removeEventListener("mouseup", this.handleMouseUp);
        window.removeEventListener("resize", this.setWidth);
    }

    @bind private handleMouseDown(event: React.MouseEvent<HTMLDivElement>): void {
        const rect = this.container.getBoundingClientRect();
        this.originX = (event.pageX - rect.left) / rect.width;
        this.brushing = true;
        event.stopPropagation();
    }

    @bind private handleMouseMove(event: MouseEvent): void {
        if (!this.container || !this.brushing) {
            return;
        }
        const { totalRange, oldestTime } = this.cachedAudio;
        const rect = this.container.getBoundingClientRect();
        const x = (event.pageX - rect.left) / rect.width;
        this.cachedAudio.selectionStart = new Date(Math.min(x, this.originX) * totalRange + oldestTime);
        this.cachedAudio.selectionEnd = new Date(Math.max(x, this.originX) * totalRange + oldestTime);
        event.stopPropagation();
    }

    @bind private handleMouseUp(): void {
        this.brushing = false;
        delete this.originX;
    }

    @bind private handleBrushChange(left: number, right: number): void {
        const { totalRange, oldestTime } = this.cachedAudio;
        this.cachedAudio.selectionStart = new Date(oldestTime + left * totalRange);
        this.cachedAudio.selectionEnd = new Date(oldestTime + right * totalRange);
    }

    @computed private get brushLeft(): number {
        const { totalRange, selectionStart, oldestTime } = this.cachedAudio;
        return (selectionStart.getTime() - oldestTime) / totalRange;
    }

    @computed private get brushRight(): number {
        const { totalRange, oldestTime, selectionEnd } = this.cachedAudio;
        return (selectionEnd.getTime() - oldestTime) / totalRange;
    }

    @bind private refContainer(div: HTMLDivElement): void {
        this.container = div;
        this.setWidth();
    }

    @bind private setWidth(): void {
        if (!this.container) {
            return;
        }
        this.width = this.container.getBoundingClientRect().width;
    }

    @bind private tickLabel(tick: number): string {
        const { oldestTime, totalRange } = this.cachedAudio;
        const secondsPerTick = ((totalRange / this.width) * tickWidth) / 1000;
        const tickTime = addSeconds(oldestTime, secondsPerTick * tick);
        if (totalRange > 60 * 60 * 24) {
            return format(tickTime, "MM-DD HH:mm");
        } else if (totalRange > 60) {
            return format(tickTime, "HH:mm");
        }
        return format(tickTime, "HH:mm:ss");
    }

    @computed private get ticks(): number {
        return Math.round(this.width / tickWidth);
    }

    @bind private renderTicks(): JSX.Element[] {
        const ticks: JSX.Element[] = [];
        for (let tick = 0; tick < this.ticks; ++tick) {
            ticks.push(
                <div className={css.tick} style={{ left: tick * tickWidth }} key={tick}>
                    <div className={css.tickLine} />
                    <div className={css.tickLabel}>{this.tickLabel(tick)}</div>
                </div>,
            );
        }
        return ticks;
    }

    public render(): JSX.Element {
        const classes = classNames("ui", "card", "fluid", css.container);
        return (
            <div className={css.tickContainer}>
                <div className={classes} ref={this.refContainer} onMouseDown={this.handleMouseDown}>
                    <div />
                    {this.cachedAudio.all.map((cachedAudio) => (
                        <CachedAudioBlock cachedAudio={cachedAudio} key={cachedAudio.id} />
                    ))}
                    {this.cachedAudio.selectionDefined && (
                        <Brush left={this.brushLeft} right={this.brushRight} onChange={this.handleBrushChange} />
                    )}
                    <div />
                </div>
                {this.renderTicks()}
            </div>
        );
    }
}
