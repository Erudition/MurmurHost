import * as React from "react";
import { inject, external } from "tsdi";
import { Link } from "react-router-dom";
import { observer } from "mobx-react";
import { computed } from "mobx";
import { List, Icon, Image } from "semantic-ui-react";
import { routeUser } from "../../routing/routing";
import * as css from "./channel-tree.scss";
import * as unkownUrl from "./unkown.png";
import { MumbleUser } from "../../../common/models/mumble-user";
import { MumbleStore } from "../../store/mumble";
import { User } from "../../../common/models/user";

@observer
@external
export class TreeUser extends React.Component<{ user: MumbleUser }> {
    @inject private readonly mumble!: MumbleStore;

    @computed private get linkedUser(): User {
        return this.mumble.getUser(this.props.user);
    }

    public render(): JSX.Element {
        const { linkedUser, props } = this;
        const { name } = props.user;
        return (
            <List.Item>
                {<Image avatar src={this.linkedUser ? this.linkedUser.avatarUrl : unkownUrl} size="mini" />}
                <List.Content verticalAlign="middle">
                    <List.Header>
                        {name}
                        {linkedUser && (
                            <Link className={css.link} to={routeUser.path(linkedUser.id)}>
                                <Icon name="linkify" /> {linkedUser.name}
                            </Link>
                        )}
                    </List.Header>
                </List.Content>
            </List.Item>
        );
    }
}
