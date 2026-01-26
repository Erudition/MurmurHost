import * as React from "react";
import { observer } from "mobx-react";
import { external, inject } from "tsdi";
import { bind } from "decko";
import { List, Image, Icon } from "semantic-ui-react";
import { routeUser } from "../../routing/routing";
import { User } from "../../../common/models/user";
import { UsersStore } from "../../store/users";
import { BrowserHistory } from "../../factories/history";

@observer
@external
export class UserList extends React.Component {
    @inject private readonly users!: UsersStore;
    @inject private readonly browserHistory!: BrowserHistory;

    @bind private handleClick(id: string): void {
        this.browserHistory.push(routeUser.path(id));
    }

    @bind private renderUser(user: User): JSX.Element {
        const { id, name, avatarUrl, enabled, admin } = user;
        return (
            <List.Item onClick={() => this.handleClick(id)}>
                <Image avatar src={avatarUrl} size="mini" />
                <List.Content>
                    <List.Header>
                        {name}
                        {!enabled && <Icon color="red" name="lock" />}
                        {admin && <Icon color="green" name="wizard" />}
                    </List.Header>
                </List.Content>
            </List.Item>
        );
    }

    public render(): JSX.Element {
        return (
            <List selection verticalAlign="middle">
                {this.users.all.map((user) => this.renderUser(user))}
            </List>
        );
    }
}
