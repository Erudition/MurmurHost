import * as React from "react";
import { bind } from "decko";
import { inject, external } from "tsdi";
import { observer } from "mobx-react";
import { computed, action, observable } from "mobx";
import { Card, Dimmer, Loader } from "semantic-ui-react";
import { PieChart, Pie } from "recharts";
import { chartColors } from "../../chart-colors";
import { StatisticsStore } from "../../store/statistics";
import { ActiveShape } from "../active-shape/active-shape";

const sourceNames = {
    recording: "Recorded",
    youtube: "YouTube",
    upload: "Uploaded",
};

@observer
@external
export class ChartSoundsPerSource extends React.Component {
    @inject private readonly statistics!: StatisticsStore;

    @observable private activeIndex = 0;

    @computed private get loading(): boolean {
        return !this.statistics.soundsPerSource;
    }

    @computed private get data(): { name: string; value: number }[] {
        if (this.loading) {
            return;
        }
        return this.statistics.soundsPerSource
            .map(({ source, sounds }, index) => ({
                name: sourceNames[source],
                value: sounds,
                fill: chartColors[index % chartColors.length],
            }))
            .sort((a, b) => a.value - b.value);
    }

    @bind
    @action
    private doPieEnter(_, index: number): void {
        this.activeIndex = index;
    }

    public render(): JSX.Element {
        return (
            <Card fluid>
                <Card.Content>Sounds per Source</Card.Content>
                <Dimmer.Dimmable as={Card.Content} dimmed={this.loading}>
                    <Dimmer active={this.loading} inverted>
                        <Loader>Loading</Loader>
                    </Dimmer>
                    <PieChart style={{ margin: "auto" }} width={500} height={300}>
                        {this.data && (
                            <Pie
                                activeIndex={this.activeIndex}
                                activeShape={ActiveShape}
                                data={this.data}
                                cx={250}
                                cy={150}
                                innerRadius={80}
                                outerRadius={110}
                                onMouseEnter={this.doPieEnter}
                                dataKey="value"
                            />
                        )}
                    </PieChart>
                </Dimmer.Dimmable>
            </Card>
        );
    }
}
