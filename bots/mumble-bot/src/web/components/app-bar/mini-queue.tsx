import * as React from "react";
import { distanceInWordsStrict, addSeconds } from "date-fns";
import { Progress } from "semantic-ui-react";
import { inject, external } from "tsdi";
import { observer } from "mobx-react";
import { computed } from "mobx";
import * as css from "./mini-queue.scss";
import { QueueStore } from "../../store/queue";

@observer
@external
export class MiniQueue extends React.Component {
    @inject private readonly queue!: QueueStore;

    @computed private get doneDate(): Date {
        return addSeconds(new Date(), this.queue.totalSeconds);
    }

    @computed private get formattedDuration(): string {
        return distanceInWordsStrict(new Date(), this.doneDate);
    }

    @computed private get queueCount(): number {
        return this.queue.queue.length;
    }

    @computed private get percent(): number {
        const fraction = this.queue.totalSeconds / this.queue.maxDurationSinceLastClear;
        return 100 - Math.round(100 * fraction);
    }

    public render(): JSX.Element {
        if (this.queueCount === 0) {
            return <span>Queue is empty.</span>;
        }
        return (
            <>
                <Progress percent={this.percent} progress active color="violet" inverted className={css.progress} />
                <span>
                    <b>{this.queueCount}</b> Items in queue. Will run for <b>{this.formattedDuration}</b>.
                </span>
            </>
        );
    }
}
