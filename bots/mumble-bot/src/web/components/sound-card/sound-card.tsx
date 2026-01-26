import * as React from "react";
import { Card } from "semantic-ui-react";
import { observer } from "mobx-react";
import { computed } from "mobx";
import { external, inject } from "tsdi";
import { SoundCardDescription } from "./description";
import { SoundCardTags } from "./tags";
import { Meta } from "./meta";
import { Buttons } from "./buttons";
import * as css from "./sound-card.scss";
import classNames from "classnames/bind";
import { Sound } from "../../../common/models/sound";
import { SoundsStore } from "../../store/sounds";

const cx = classNames.bind(css);

declare const baseUrl: string;

@observer
@external
export class SoundCard extends React.Component<{ id: string; zIndex: number; mini?: boolean }> {
    @inject private readonly sounds!: SoundsStore;

    @computed private get sound(): Sound {
        return this.sounds.sounds.get(this.props.id);
    }

    private get visualizationUrl(): string {
        return `${baseUrl}/sound/${this.sound.id}/visualized`;
    }

    public render(): JSX.Element {
        const { sound, visualizationUrl } = this;
        const { zIndex, mini } = this.props;
        return (
            <Card fluid className={css.card} style={{ zIndex }}>
                <Card.Content className={cx({ sound: true, mini })}>
                    <div style={{ backgroundImage: `url(${visualizationUrl})` }} className={css.background} />
                    <div className={css.gradient} />
                    <Card.Description className={css.description}>
                        <SoundCardDescription sound={sound} />
                    </Card.Description>
                    {!mini && <SoundCardTags sound={sound} />}
                </Card.Content>
                {!mini && (
                    <Card.Content>
                        <Meta sound={sound} />
                    </Card.Content>
                )}
                <Card.Content extra>
                    <Buttons sound={sound} />
                </Card.Content>
            </Card>
        );
    }
}
