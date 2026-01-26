import * as React from "react";
import { Icon } from "semantic-ui-react";
import { Sound } from "../../../common/models/sound";
import { MiniUserBadge } from "../mini-user-badge/mini-user-badge";

export function SoundSource({ sound }: { sound: Sound }): JSX.Element {
    const { source, user } = sound;
    switch (source) {
        case "recording":
            return (
                <span>
                    <Icon name="microphone" /> <MiniUserBadge user={user} />
                </span>
            );
        case "youtube":
            return (
                <span>
                    <Icon name="youtube play" /> YouTube
                </span>
            );
        default:
        case "upload":
            return (
                <span>
                    <Icon name="upload" /> Uploaded
                </span>
            );
    }
}
