import * as React from "react";
import { observer } from "mobx-react";
import { external, inject } from "tsdi";
import { bind } from "decko";
import { Checkbox, Form } from "semantic-ui-react";
import { MumbleUser } from "../../../common/models/mumble-user";
import { MumbleStore } from "../../store/mumble";

@observer
@external
export class MumbleLinker extends React.Component {
    @inject private readonly mumble!: MumbleStore;

    @bind private renderMumbleUser(mumbleUser: MumbleUser): JSX.Element {
        const { id, name } = mumbleUser;
        const disabled = !this.mumble.isLinkable(mumbleUser);
        const checked = this.mumble.isLinkedToThisUser(mumbleUser);
        return (
            <Form.Field key={id}>
                <Checkbox
                    label={name}
                    disabled={disabled}
                    checked={checked}
                    onClick={() => this.mumble.toggle(mumbleUser)}
                />
            </Form.Field>
        );
    }

    public render(): JSX.Element {
        return <Form>{this.mumble.allUsers.map((user) => this.renderMumbleUser(user))}</Form>;
    }
}
