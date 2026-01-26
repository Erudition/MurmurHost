import * as React from "react";
import { Icon, MenuItem } from "semantic-ui-react";
import { inject, external } from "tsdi";
import { observer } from "mobx-react";
import { computed } from "mobx";
import { SemanticCOLORS, SemanticICONS } from "semantic-ui-react";
import { MumbleConnectionStatus } from "../../../common/mumble-connection-status";
import { LiveWebsocket } from "../../store/live-websocket";

@observer
@external
export class MumbleStatus extends React.Component {
    @inject private readonly live!: LiveWebsocket;

    @computed private get icon(): SemanticICONS {
        switch (this.live.mumbleStatus) {
            case MumbleConnectionStatus.CONNECTING:
                return "spinner";
            case MumbleConnectionStatus.DISCONNECTED:
                return "unlinkify";
            case MumbleConnectionStatus.HEALTHY:
                return "check";
            case MumbleConnectionStatus.ERROR:
                return "warning sign";
        }
    }

    @computed private get info(): string {
        switch (this.live.mumbleStatus) {
            case MumbleConnectionStatus.CONNECTING:
                return "Bot (re-)connecting";
            case MumbleConnectionStatus.DISCONNECTED:
                return "Bot disconnected";
            case MumbleConnectionStatus.HEALTHY:
                return "Bot healthy";
            case MumbleConnectionStatus.ERROR:
                return "Bot unhealthy";
        }
    }

    @computed private get color(): SemanticCOLORS | undefined {
        switch (this.live.mumbleStatus) {
            case MumbleConnectionStatus.CONNECTING:
                return "blue";
            case MumbleConnectionStatus.DISCONNECTED:
                return "yellow";
            case MumbleConnectionStatus.ERROR:
                return "red";
            case MumbleConnectionStatus.HEALTHY:
                return;
        }
    }

    @computed private get loading(): boolean {
        return this.live.mumbleStatus === MumbleConnectionStatus.CONNECTING;
    }

    @computed private get disabled(): boolean {
        return this.live.mumbleStatus === MumbleConnectionStatus.HEALTHY;
    }

    public render(): JSX.Element {
        if (this.live.loading) {
            return <></>;
        }
        return (
            <MenuItem
                icon={<Icon color={this.color} name={this.icon} loading={this.loading} />}
                content={this.info}
                disabled={this.disabled}
            />
        );
    }
}
