import { Sound } from "../common/models/sound";
import { Tag } from "../common/models/tag";
import { Token } from "../common/models/token";
import { api } from "./api";

export async function createTag(name: string, token: Token): Promise<Tag> {
    const response = await api().post("/tags").set("authorization", `Bearer ${token.id}`).send({ name });
    return response.body.data;
}

export async function tagSound(sound: Sound, tag: Tag, token: Token): Promise<unknown> {
    const response = await api()
        .post(`/sound/${sound.id}/tags`)
        .set("authorization", `Bearer ${token.id}`)
        .send({ id: tag.id });
    return response.body.data;
}
