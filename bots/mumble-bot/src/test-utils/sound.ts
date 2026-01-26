/* eslint-disable @typescript-eslint/no-explicit-any */
import { createUser } from "./user";
import { api } from "./api";
import { Sound } from "../common/models/sound";
import { User } from "../common/models/user";
import { Database } from "../server/database";

const defaultSound = {
    description: "Some sound",
    used: 17,
    source: "recording",
    duration: 13,
};

export async function createSound(sound?: Sound): Promise<Sound> {
    return await tsdi
        .get(Database)
        .getRepository(Sound)
        .save({ ...defaultSound, ...sound } as Sound);
}

export async function createSoundWithCreatorAndSpeaker(
    data?: Sound,
): Promise<{ sound: Sound; creator: User; speaker: User }> {
    const user = await createUser({ name: "Speaker", email: "speaker@example.com" } as User);
    const creator = await createUser({ name: "Creator", email: "creator@example.com" } as User);
    const sound = await createSound({ ...data, user, creator } as Sound);
    return { sound, creator, speaker: user };
}

export async function getSound(id: string, token: string): Promise<any> {
    const response = await api().get(`/sound/${id}`).set("authorization", `Bearer ${token}`);
    return response.body.data;
}

export async function rateSound(id: string, token: string, stars: number): Promise<any> {
    return await api().post(`/sound/${id}/ratings`).set("authorization", `Bearer ${token}`).send({ stars });
}
