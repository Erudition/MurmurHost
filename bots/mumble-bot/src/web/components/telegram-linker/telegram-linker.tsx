import * as React from "react";
import { observer } from "mobx-react";
import { external, inject } from "tsdi";
import { bind } from "decko";
import { Checkbox, Form } from "semantic-ui-react";
import { TelegramUser } from "../../../common/models/telegram-user";
import { TelegramUserStore } from "../../store/telegram-users";

@observer
@external
export class TelegramLinker extends React.Component {
    @inject private readonly telegramUserStore!: TelegramUserStore;

    @bind private renderTelegramUser(telegramUser: TelegramUser): JSX.Element {
        const { id, telegramName } = telegramUser;
        const disabled = !this.telegramUserStore.isLinkable(telegramUser);
        const checked = this.telegramUserStore.isLinkedToThisUser(telegramUser);
        return (
            <Form.Field key={id}>
                <Checkbox
                    label={telegramName}
                    disabled={disabled}
                    checked={checked}
                    onClick={() => this.telegramUserStore.toggle(telegramUser.id)}
                />
            </Form.Field>
        );
    }

    public render(): JSX.Element {
        return <Form>{this.telegramUserStore.all.map((user) => this.renderTelegramUser(user))}</Form>;
    }
}
