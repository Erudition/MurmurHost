import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, inject, initialize } from "tsdi";
import { DropdownItemProps } from "semantic-ui-react";
import { Users } from "../../common/controllers/users";
import { User } from "../../common/models/user";
import { LoginStore } from "./login";

@component
export class UsersStore {
    @inject private readonly usersController!: Users;
    @inject private readonly loginStore!: LoginStore;

    @observable public loading = true;
    @observable private users: Map<string, User> = new Map();

    @initialize
    @bind
    @action
    protected async loadUsers(): Promise<User[]> {
        await this.loginStore.onLogin$.toPromise();
        const users = await this.usersController.listUsers();
        users.forEach((user) => {
            this.users.set(user.id, user);
        });
        this.loading = false;
        return users;
    }

    @computed
    public get all(): User[] {
        return Array.from(this.users.values());
    }

    @computed
    public get alphabetical(): User[] {
        return this.all.sort((a, b) => {
            if (a.name > b.name) {
                return 1;
            }
            if (a.name < b.name) {
                return -1;
            }
            return 0;
        });
    }

    @bind public byId(id: string): User {
        return this.users.get(id);
    }

    @bind @action public async updateUser(id: string, user: User): Promise<void> {
        this.users.set(id, await this.usersController.updateUser(id, user));
    }

    @computed public get dropdownOptions(): DropdownItemProps[] {
        return this.all.map((user) => ({
            key: user.id,
            value: user.id,
            text: user.name,
        }));
    }
}
