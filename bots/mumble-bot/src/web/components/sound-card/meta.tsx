import * as React from "react";
import { observer } from "mobx-react";
import { action } from "mobx";
import { bind } from "decko";
import { external, inject } from "tsdi";
import { Icon, Card, Rating } from "semantic-ui-react";
import { distanceInWordsToNow } from "date-fns";
import * as css from "./sound-card.scss";
import classNames from "classnames/bind";
import { Sound } from "../../../common/models/sound";
import { SoundsStore } from "../../store/sounds";
import { MiniUserBadge } from "../mini-user-badge/mini-user-badge";
import { SoundSource } from "../sound-source/sound-source";

const cx = classNames.bind(css);

export interface MetaProps {
    sound: Sound;
}

@external
@observer
export class Meta extends React.Component<MetaProps> {
    @inject private readonly sounds!: SoundsStore;

    @bind @action private async handleRate(
        _: React.MouseEvent<HTMLDivElement>,
        { rating }: { rating: number },
    ): Promise<void> {
        await this.sounds.rate(this.props.sound.id, rating);
    }

    public render(): JSX.Element {
        const { creator, created, duration, rating } = this.props.sound;
        return (
            <>
                <Card.Meta>
                    <div className={css.flexContainer}>
                        <span className={css.metaTag}>
                            <SoundSource sound={this.props.sound} />
                        </span>
                        <span className={css.metaTag}>
                            <Icon name="add user" /> <MiniUserBadge user={creator} />
                        </span>
                        <span className={css.metaTag}>
                            <Icon name="add to calendar" /> {distanceInWordsToNow(created)} ago
                        </span>
                        <span className={css.metaTag}>
                            <Icon name="time" /> {duration.toFixed(2)}s
                        </span>
                        <span className={cx("metaTag", "rating")}>
                            <Rating icon="star" onRate={this.handleRate} maxRating={5} rating={rating} />
                        </span>
                    </div>
                </Card.Meta>
            </>
        );
    }
}
