import { User } from "../common/models/user";
import { hash } from "../common/utils/hash";
import { Database } from "../server/database";
import { api } from "./api";

const defaultUser = {
    name: "someone",
    email: "some@example.com",
    password: "some secure password",
};

export async function createUserManually(data?: User, enabled = true, admin = false): Promise<User> {
    const combined = { ...defaultUser, ...data, enabled, admin };
    const password = hash(combined.password);
    const user = await tsdi
        .get(Database)
        .getRepository(User)
        .save({ ...combined, password });
    return user;
}

export async function createUser(data?: User, enable = true, admin = false): Promise<User> {
    const response = await api()
        .post("/user")
        .send({ ...defaultUser, ...data });
    const user = response.body.data;
    if (enable) {
        await tsdi.get(Database).getRepository(User).update(user.id, { enabled: true });
        user.enabled = true;
    }
    if (admin) {
        await tsdi.get(Database).getRepository(User).update(user.id, { admin: true });
        user.admin = true;
    }
    return user;
}
