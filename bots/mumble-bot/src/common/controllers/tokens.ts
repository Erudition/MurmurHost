import { controller, route, created, body, unauthorized, populate, noauth } from "hyrest";
import { inject, component } from "tsdi";
import { Database } from "../../server/database";
import { Token } from "../models/token";
import { User } from "../models/user";
import { login, owner } from "../scopes";

@controller
@component
export class Tokens {
    @inject public readonly db!: Database;

    @(route("POST", "/token").dump(Token, owner))
    @noauth
    public async createToken(@body(login) credentials: User): Promise<Token> {
        const user = await this.db.getRepository(User).findOne(credentials);
        if (!user) {
            return unauthorized<Token>("Invalid credentials.");
        }
        if (!user.enabled) {
            return unauthorized<Token>("User is disabled.");
        }
        const newToken = await this.db.getRepository(Token).save(populate(owner, Token, { user }));
        return created(newToken);
    }
}
