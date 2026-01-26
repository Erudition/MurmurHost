import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, initialize, inject } from "tsdi";
import { LoginStore } from "./login";
import { User } from "../../common/models/user";
import { UsersStore } from "./users";
import { TelegramUsers } from "../../common/controllers/telegram-users";
import { TelegramUser } from "../../common/models/telegram-user";

@component
export class TelegramUserStore {
    @inject private readonly telegramUsers!: TelegramUsers;
    @inject private readonly login!: LoginStore;
    @inject private readonly users!: UsersStore;

    @observable public knownUsers: Map<string, TelegramUser> = new Map();

    @initialize
    protected async initialize(): Promise<void> {
        await this.login.onLogin$.toPromise();
        (await this.telegramUsers.getTelegramUsers()).forEach((telegramUser) => {
            this.knownUsers.set(telegramUser.id, telegramUser);
        });
    }

    @computed public get all(): TelegramUser[] {
        return Array.from(this.knownUsers.values());
    }

    @computed public get linkableUsers(): TelegramUser[] {
        return this.all.filter(this.isLinkable);
    }

    @computed public get linkedToThisUser(): TelegramUser[] {
        return this.all.filter((telegramUser) => telegramUser.user?.id === this.login.userId);
    }

    @bind public isLinkable(telegramUser: TelegramUser): boolean {
        return !telegramUser.user?.id || this.isLinkedToThisUser(telegramUser);
    }

    @bind public isLinkedToThisUser(telegramUser: TelegramUser): boolean {
        return telegramUser.user?.id === this.login.userId;
    }

    @bind public getUser(telegramUser: TelegramUser): User | undefined {
        if (!telegramUser.user) {
            return;
        }
        return this.users.byId(telegramUser.user.id);
    }

    @bind public getTelegramUser(user: User): TelegramUser {
        return this.all.find((telegramUser) => telegramUser.user?.id === user.id);
    }

    @bind @action public async link(id: string): Promise<void> {
        const telegramUser = await this.telegramUsers.updateTelegramUser(id, {
            user: { id: this.login.userId } as User,
        });
        this.knownUsers.set(telegramUser.id, telegramUser);
    }

    @bind @action public async unlink(id: string): Promise<void> {
        const telegramUser = await this.telegramUsers.updateTelegramUser(id, {
            user: null,
        });
        this.knownUsers.set(telegramUser.id, telegramUser);
    }

    @bind public async toggle(id: string): Promise<void> {
        if (this.isLinkedToThisUser(this.knownUsers.get(id))) {
            await this.unlink(id);
            return;
        }
        await this.link(id);
    }
}
