import { observable, action, computed } from "mobx";
import { bind } from "decko";
import { component, initialize, inject } from "tsdi";
import { Users } from "../../common/controllers/users";
import { User } from "../../common/models/user";
import { LoginStore } from "./login";

@component
export class OwnUserStore {
    @inject private readonly users!: Users;
    @inject private readonly login!: LoginStore;

    @observable public user: User;

    @initialize
    @bind
    @action
    public async loadUser(): Promise<void> {
        await this.login.onLogin$.toPromise();
        if (this.login.loggedIn) {
            this.user = await this.users.getUser(this.login.userId);
        }
    }

    @computed public get admin(): boolean {
        if (!this.user) {
            return false;
        }
        return this.user.admin;
    }
}
