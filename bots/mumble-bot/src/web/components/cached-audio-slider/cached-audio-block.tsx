import * as React from "react";
import classNames from "classnames";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { computed } from "mobx";
import * as css from "./cached-audio-block.scss";
import { CachedAudio } from "../../../common/models/cached-audio";
import { CachedAudioStore } from "../../store/cached-audio";

@external
@observer
export class CachedAudioBlock extends React.Component<{ cachedAudio: CachedAudio }> {
    @inject private readonly cachedAudio!: CachedAudioStore;

    @computed private get left(): number {
        const { cachedAudio, props } = this;
        const { oldestTime, totalRange } = cachedAudio;
        return (props.cachedAudio.date.getTime() - oldestTime) / totalRange;
    }

    @computed private get width(): number {
        return (this.props.cachedAudio.duration * 1000) / this.cachedAudio.totalRange;
    }

    public render(): JSX.Element {
        const left = `${this.left * 100}%`;
        const width = `${this.width * 100}%`;
        const classes = classNames(css.block);
        return <div className={classes} style={{ left, width }} />;
    }
}
