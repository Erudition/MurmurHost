import { copy } from "fs-extra";
import { fft, util } from "fft-js";
import { populate } from "hyrest";
import { ServerConfig } from "../../../config/server-config";
import { AudioCache } from "../../../server/audio-cache";
import { AudioOutput } from "../../../server/audio-output";
import { Mumble } from "../../../server/mumble";
import { api } from "../../../test-utils/api";
import { startDb, stopDb } from "../../../test-utils/db";
import { createSoundWithCreatorAndSpeaker } from "../../../test-utils/sound";
import { createUserWithToken } from "../../../test-utils/token";
import { CachedAudio } from "../../models/cached-audio";
import { Playlist } from "../../models/playlist";
import { Sound } from "../../models/sound";
import { Token } from "../../models/token";
import { world } from "../../scopes";
import { createPlaylist } from "../../../test-utils/playlist";
import { User } from "../../models/user";

describe("queue controller", () => {
    let token: Token;
    let user: User;
    let sound: Sound;
    let mumble: Mumble;
    let audioOutput: AudioOutput;
    let voice: number[];

    beforeEach(startDb);
    afterEach(stopDb);

    beforeEach(async () => {
        const userAndToken = await createUserWithToken();
        token = userAndToken.token;
        user = userAndToken.user;
        sound = (await createSoundWithCreatorAndSpeaker({ duration: 1 } as Sound)).sound;
        await copy(
            `${__dirname}/../../../__fixtures__/sin-short.mp3`,
            `${tsdi.get(ServerConfig).soundsDir}/${sound.id}`,
        );
        mumble = tsdi.get(Mumble);
        audioOutput = tsdi.get(AudioOutput);

        voice = [];
        mumble.inputStream().on("data", (data: Buffer) => {
            for (let i = 0; i < data.length; i += 2) {
                const num = data.readInt16LE(i);
                voice.push((num / Math.pow(2, 16)) * 2 - 1);
            }
        });
    });

    describe("POST /queue", () => {
        it("responds 401 without a valid token", async () => {
            const response = await api().post("/queue");
            expect(response.body).toEqual({ message: "Unauthorized." });
            expect(response.status).toBe(401);
        });

        describe(`with type="sound"`, () => {
            it("responds 400 with no sound specified", async () => {
                const requestQueueItem = { type: "sound", pitch: 50 };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({ message: `Must specify "sound" if type is set to "sound".` });
            });

            it("responds 400 with an unkown sound specified", async () => {
                const requestQueueItem = {
                    type: "sound",
                    sound: { id: "04b6416f-812e-4424-8bf8-fe0e145af861" },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({ message: `No sound with id "04b6416f-812e-4424-8bf8-fe0e145af861".` });
            });

            it("enqueues a sound", async () => {
                const requestQueueItem = {
                    type: "sound",
                    sound: { id: sound.id },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(201);
                const resultQueueItem = {
                    ...requestQueueItem,
                    user: { id: user.id },
                };
                expect(response.body).toMatchObject({ data: resultQueueItem });
                const updatedSoundResponse = await api()
                    .get(`/sound/${sound.id}`)
                    .set("authorization", `Bearer ${token.id}`);
                expect(updatedSoundResponse.body.data.used).toBe(sound.used + 1);
                await new Promise((resolve) => {
                    audioOutput.once("shift", (item) => {
                        expect(voice.length).toMatchSnapshot();
                        expect(item).toMatchObject(resultQueueItem);
                        resolve();
                    });
                });
            });
        });

        describe(`with type="cached audio"`, () => {
            it("responds 400 with no cached audio specified", async () => {
                const requestQueueItem = { type: "cached audio", pitch: 50 };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({
                    message: `Must specify "cachedAudio" if type is set to "cached audio".`,
                });
            });

            it("responds 400 with an unkown cached audio specified", async () => {
                const requestQueueItem = {
                    type: "cached audio",
                    cachedAudio: { id: "04b6416f-812e-4424-8bf8-fe0e145af861" },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({
                    message: `No cached audio with id "04b6416f-812e-4424-8bf8-fe0e145af861".`,
                });
            });

            it("enqueues a cached audio", async () => {
                const cachedAudio = {
                    date: new Date("2018-11-15Z10:00:00"),
                    user,
                    id: "0edf2ba3-d372-4ccf-8b85-f475423747cb",
                    duration: 15,
                    amplitude: 38,
                };
                await copy(
                    `${__dirname}/../../../__fixtures__/sin-short.mp3`,
                    `${tsdi.get(ServerConfig).tmpDir}/${cachedAudio.id}`,
                );
                await tsdi.get(AudioCache).add(populate(world, CachedAudio, cachedAudio));
                const requestQueueItem = {
                    type: "cached audio",
                    cachedAudio: { id: cachedAudio.id },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(201);
                const resultQueueItem = {
                    ...requestQueueItem,
                    user: { id: user.id },
                };
                expect(response.body).toMatchObject({ data: resultQueueItem });
                await new Promise((resolve) => {
                    audioOutput.once("shift", (item) => {
                        expect(voice.length).toMatchSnapshot();
                        expect(item).toMatchObject(resultQueueItem);
                        resolve();
                    });
                });
            });
        });

        describe(`with type="playlist"`, () => {
            it("responds 400 with no playlist specified", async () => {
                const requestQueueItem = { type: "playlist", pitch: 50 };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({ message: `Must specify "playlist" if type is set to "playlist".` });
            });

            it("responds 400 with an unkown playlist specified", async () => {
                const requestQueueItem = {
                    type: "playlist",
                    playlist: { id: "04b6416f-812e-4424-8bf8-fe0e145af861" },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(400);
                expect(response.body).toEqual({
                    message: `No playlist with id "04b6416f-812e-4424-8bf8-fe0e145af861".`,
                });
            });

            it("enqueues a playlist", async () => {
                const playlist = await createPlaylist(user, 0, {} as Playlist, sound, sound);
                const requestQueueItem = {
                    type: "playlist",
                    playlist: { id: playlist.id },
                    pitch: 50,
                };
                const response = await api()
                    .post(`/queue`)
                    .set("authorization", `Bearer ${token.id}`)
                    .send(requestQueueItem);
                expect(response.status).toBe(201);
                const resultQueueItem = {
                    ...requestQueueItem,
                    user: { id: user.id },
                };
                expect(response.body).toMatchObject({ data: resultQueueItem });
                await new Promise((resolve) => {
                    audioOutput.once("shift", (item) => {
                        expect(voice.length).toMatchSnapshot();
                        expect(item).toMatchObject(resultQueueItem);
                        resolve();
                    });
                });
            });

            [-200, 600].forEach((pitch) => {
                it(`enqueues a playlist with pitch ${pitch}`, async () => {
                    const playlist = await createPlaylist(user, pitch, {} as Playlist, sound, sound);
                    const requestQueueItem = {
                        type: "playlist",
                        playlist: { id: playlist.id },
                    };
                    const response = await api()
                        .post(`/queue`)
                        .set("authorization", `Bearer ${token.id}`)
                        .send(requestQueueItem);
                    expect(response.status).toBe(201);
                    const resultQueueItem = {
                        ...requestQueueItem,
                        user: { id: user.id },
                    };
                    expect(response.body).toMatchObject({ data: resultQueueItem });
                    await new Promise((resolve) => {
                        audioOutput.once("shift", (item) => {
                            expect(voice.length).toMatchSnapshot();
                            const phasors = fft(voice.slice(0, Math.pow(2, 15)));
                            const frequencies = util.fftFreq(phasors, 48000);
                            const magnitudes = util.fftMag(phasors);
                            let highest: number;
                            let highestIndex: number;
                            for (let i = 1; i < magnitudes.length; ++i) {
                                if (highest === undefined || magnitudes[i] > highest) {
                                    highest = magnitudes[i];
                                    highestIndex = i;
                                }
                            }
                            expect({
                                magnitude: Math.round(highest),
                                frequency: Math.round(frequencies[highestIndex]),
                            }).toMatchSnapshot();
                            expect(item).toMatchObject(resultQueueItem);
                            resolve();
                        });
                    });
                });
            });
        });
    });
});
