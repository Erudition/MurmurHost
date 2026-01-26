import { observable, action } from "mobx";
import { bind } from "decko";
import { component, inject } from "tsdi";
import { Users } from "../../common/controllers/users";
import { User } from "../../common/models/user";

@component
export class SignupStore {
    @inject private readonly users!: Users;

    @observable public signupResult: Boolean;

    @bind
    @action
    public async signup(email: string, password: string, name: string): Promise<User> {
        const response = await this.users.createUser({ email, password, name } as User);
        if (response) {
            this.signupResult = true;
        }
        return response;
    }
}
