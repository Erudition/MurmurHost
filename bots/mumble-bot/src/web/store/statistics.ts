import { observable } from "mobx";
import { initialize, component, inject } from "tsdi";
import { Statistics } from "../../common/controllers/statistics";
import { CreationsPerSingleUser } from "../../common/models/statistics/creations-per-user";
import { StatisticOverview } from "../../common/models/statistics/overview";
import { PlaybacksPerSingleUser } from "../../common/models/statistics/playbacks-per-user";
import { RecordingsPerSingleUser } from "../../common/models/statistics/recordings-per-user";
import { SoundsPerSingleMonth } from "../../common/models/statistics/sounds-per-month";
import { SoundsPerSingleSource } from "../../common/models/statistics/sounds-per-source";

@component
export class StatisticsStore {
    @inject private readonly statisticsController!: Statistics;

    @observable public overview: StatisticOverview = undefined;
    @observable public soundsPerSource: SoundsPerSingleSource[] = undefined;
    @observable public recordingsPerUser: RecordingsPerSingleUser[] = undefined;
    @observable public creationsPerUser: CreationsPerSingleUser[] = undefined;
    @observable public playbacksPerUser: PlaybacksPerSingleUser[] = undefined;
    @observable public soundsPerMonth: SoundsPerSingleMonth[] = undefined;

    @initialize protected async initialize(): Promise<void> {
        const overview = await this.statisticsController.getOverview();
        const { soundsPerSource } = await this.statisticsController.getSoundsPerSource();
        const { recordingsPerUser } = await this.statisticsController.getRecordingsPerUser();
        const { creationsPerUser } = await this.statisticsController.getCreationsPerUser();
        const { playbacksPerUser } = await this.statisticsController.getPlaybacksPerUser();
        const { soundsPerMonth } = await this.statisticsController.getSoundsPerMonth();
        this.overview = overview;
        this.soundsPerSource = soundsPerSource;
        this.recordingsPerUser = recordingsPerUser;
        this.creationsPerUser = creationsPerUser;
        this.playbacksPerUser = playbacksPerUser;
        this.soundsPerMonth = soundsPerMonth;
    }
}
