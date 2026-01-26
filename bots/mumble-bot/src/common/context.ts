import { inject, external } from "tsdi";
import { Request } from "express";
import { Database } from "../server/database";
import { User } from "./models/user";
import { getAuthTokenId } from "./utils/authorization";
import { Validation } from "./controllers/validation";

@external
export class Context {
    @inject public readonly validation!: Validation;
    @inject private readonly db!: Database;

    private authTokenId: string;

    constructor(req: Request) {
        const id = getAuthTokenId(req);
        this.authTokenId = id;
    }

    public async currentUser(): Promise<User> {
        const id = this.authTokenId;
        if (!id) {
            return;
        }
        return await this.db
            .getRepository(User)
            .createQueryBuilder("user")
            .innerJoin("user.tokens", "token")
            .where("token.id=:id", { id })
            .getOne();
    }
}
