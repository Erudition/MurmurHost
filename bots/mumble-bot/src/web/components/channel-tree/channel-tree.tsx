import * as React from "react";
import { inject, external } from "tsdi";
import { observer } from "mobx-react";
import { List } from "semantic-ui-react";
import { TreeChannel } from "./tree-channel";
import { MumbleStore } from "../../store/mumble";

@observer
@external
export class ChannelTree extends React.Component {
    @inject private readonly mumble!: MumbleStore;

    public render(): JSX.Element {
        const { channelTree } = this.mumble;
        if (!channelTree) {
            return null;
        }
        return (
            <List>
                <TreeChannel channel={channelTree} />
            </List>
        );
    }
}
