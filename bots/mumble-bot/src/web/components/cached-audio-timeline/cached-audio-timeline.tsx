import * as React from "react";
import classNames from "classnames";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { observable, computed } from "mobx";
import { bind } from "decko";
import { format, addSeconds } from "date-fns";
import { CachedAudioTimelineBlock } from "./cached-audio-timeline-block";
import * as css from "./cached-audio-timeline.scss";
import { User } from "../../../common/models/user";
import { CachedAudioStore } from "../../store/cached-audio";

const tickWidth = 100;

@external
@observer
export class CachedAudioTimeline extends React.Component<{ user: User }> {
    @inject private readonly cachedAudio!: CachedAudioStore;

    @observable private width = 0;

    private timelineDiv: HTMLDivElement;

    public componentDidMount(): void {
        window.addEventListener("resize", this.setWidth);
    }

    public componentWillUnmount(): void {
        window.removeEventListener("resize", this.setWidth);
    }

    @bind private refTimeline(div: HTMLDivElement): void {
        this.timelineDiv = div;
        this.setWidth();
    }

    @computed private get ticks(): number {
        return Math.round(this.width / tickWidth);
    }

    @bind private setWidth(): void {
        if (!this.timelineDiv) {
            return;
        }
        this.width = this.timelineDiv.getBoundingClientRect().width;
    }

    @bind private tickLabel(tick: number): string {
        const { selectionStart, selectedRange } = this.cachedAudio;
        const secondsPerTick = ((selectedRange / this.width) * tickWidth) / 1000;
        const tickTime = addSeconds(selectionStart, secondsPerTick * tick);
        if (selectedRange > 60 * 60 * 24) {
            return format(tickTime, "MM-DD HH:mm");
        } else if (selectedRange > 60) {
            return format(tickTime, "HH:mm");
        }
        return format(tickTime, "HH:mm:ss");
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
        return (
            <div className={css.wrapper}>
                <div className={css.name}>
                    <p>{this.props.user.name}</p>
                </div>
                <div className={css.tickContainer}>
                    <div ref={this.refTimeline} className={classNames(css.timeline, "ui", "card", "fluid")}>
                        <div />
                        {this.cachedAudio.inSelectionByUser(this.props.user).map((cachedAudio) => (
                            <CachedAudioTimelineBlock cachedAudio={cachedAudio} key={cachedAudio.id} />
                        ))}
                        <div />
                    </div>
                    {this.renderTicks()}
                </div>
            </div>
        );
    }
}
