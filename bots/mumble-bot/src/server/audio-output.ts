import { info, error, warn, verbose } from "winston";
import { InputStream as MumbleInputStream } from "mumble";
import FFMpeg, { FfmpegCommand } from "fluent-ffmpeg";
import Sox from "sox-stream";
import { inject, component, initialize, destroy } from "tsdi";
import { stat } from "fs-extra";
import { EventEmitter } from "events";
import { Mumble } from "./mumble";
import { bind } from "decko";
import { Database } from "./database";
import { Playlist } from "../common/models/playlist";
import { QueueItem } from "../common/models/queue-item";
import { MumbleConnectionStatus } from "../common/mumble-connection-status";
import { ServerConfig } from "../config/server-config";

const audioFreq = 48000;
const msInS = 1000;

interface PlaybackInfo {
    filename: string;
    pitch: number;
    echo: number;
}

/**
 * Audio output for the bot. This class handles the whole audio output,
 * including both TTS and sounds.
 */
@component
export class AudioOutput extends EventEmitter {
    @inject private readonly config!: ServerConfig;
    @inject private readonly db!: Database;
    @inject private readonly mumble!: Mumble;

    public busy = false;
    public queue: QueueItem[] = [];

    private mumbleStream: MumbleInputStream;
    private stopped = false;
    private ffmpeg: FfmpegCommand;
    private sox: NodeJS.ReadWriteStream;

    private transcodeTimeout: NodeJS.Timer;

    @bind private initializeInputStream(): void {
        this.mumbleStream = this.mumble.inputStream();
    }

    @initialize
    protected initialize(): void {
        this.initializeInputStream();
        this.mumble.on("status change", ({ status }: { status: MumbleConnectionStatus }) => {
            if (status === MumbleConnectionStatus.HEALTHY) {
                this.initializeInputStream();
            }
        });
    }

    /**
     * Plays the file.
     * @param filename The filename of the file to be played.
     * @param pitch The pitch to which the audio should be transformed.
     */
    private play({ filename, pitch, echo }: PlaybackInfo): Promise<undefined> {
        return new Promise(async (resolve, reject) => {
            let samplesTotal = 0;
            const startTime = Date.now();
            const effects: Sox.Effect[] = [];
            try {
                if (echo !== 0) {
                    effects.push(["echo", "0.8", "0.7", `${echo}`, "0.4"]);
                }
                if (pitch !== 0) {
                    effects.push(["pitch", `${pitch}`]);
                }
                const result = await stat(filename);
                if (!result.isFile()) {
                    error(`File ${filename} is not a regular file.`);
                    return reject();
                }
                this.ffmpeg = FFMpeg(filename).format("s16le").audioChannels(1).audioFrequency(audioFreq);
                this.ffmpeg.on("error", (err) => {
                    error(`Error decoding file ${filename}`, err);
                    reject();
                });
                this.sox = Sox({
                    input: {
                        endian: "little",
                        bits: 16,
                        channels: 1,
                        rate: 48000,
                        type: "raw",
                        encoding: "signed-integer",
                    },
                    output: {
                        endian: "little",
                        bits: 16,
                        channels: 1,
                        rate: 48000,
                        type: "raw",
                        encoding: "signed-integer",
                    },
                    effects,
                });
                this.sox
                    .on("error", (err) => error(`Error processing file "${filename}" with sox.`, err))
                    .on("data", (chunk: Buffer) => {
                        samplesTotal += chunk.length / 2;
                        try {
                            this.mumbleStream.write(chunk);
                        } catch (err) {
                            warn("Writing to mumble stream failed", err.message);
                        }
                    })
                    .on("end", () => {
                        if (this.stopped) {
                            return;
                        }
                        const timeAlreadyTaken = Date.now() - startTime;
                        const totalTime = (samplesTotal / audioFreq) * msInS;
                        const waitTime = totalTime - timeAlreadyTaken;
                        this.transcodeTimeout = global.setTimeout(resolve, waitTime);
                    });
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                (this.ffmpeg as any).stream().pipe(this.sox);
            } catch (err) {
                error(`Error reading file ${filename}`, err);
                reject();
            }
        });
    }

    /**
     * Clear the whole queue and stop current playback.
     */
    public clear(): void {
        if (this.transcodeTimeout) {
            clearTimeout(this.transcodeTimeout);
        }
        if (this.ffmpeg) {
            this.ffmpeg.kill("1");
        }
        this.queue = [];
        this.busy = false;
        this.mumbleStream.close();
        this.mumbleStream = this.mumble.inputStream();
        this.emit("clear");
    }

    private async playbackInfos(queueItem: QueueItem): Promise<PlaybackInfo[]> {
        switch (queueItem.type) {
            case "sound":
                return [
                    {
                        filename: `${this.config.soundsDir}/${queueItem.sound.id}`,
                        pitch: queueItem.pitch,
                        echo: queueItem.echo,
                    },
                ];
            case "cached audio":
                return [
                    {
                        filename: `${this.config.tmpDir}/${queueItem.cachedAudio.id}`,
                        pitch: queueItem.pitch,
                        echo: queueItem.echo,
                    },
                ];
            case "playlist": {
                const playlist = await this.db
                    .getRepository(Playlist)
                    .createQueryBuilder("playlist")
                    .where("playlist.id = :id", { id: queueItem.playlist.id })
                    .leftJoinAndSelect("playlist.entries", "entry")
                    .leftJoinAndSelect("entry.sound", "sound")
                    .orderBy("entry.position", "ASC")
                    .getOne();
                return playlist.entries.map(({ sound, pitch, echo }) => ({
                    filename: `${this.config.soundsDir}/${sound.id}`,
                    pitch,
                    echo,
                }));
            }
            default:
                return [];
        }
    }

    /**
     * Start processing the next item in the queue.
     */
    private async next(): Promise<void> {
        if (this.busy) {
            return;
        }
        this.busy = true;
        while (this.queue.length > 0 && !this.stopped) {
            const current = this.queue.shift();
            for (const playbackInfo of await this.playbackInfos(current)) {
                await this.play(playbackInfo);
            }
            this.emit("shift", current);
        }
        this.busy = false;
    }

    /**
     * Enqueue a new sound, playlist or cached audio.
     *
     * @param queueItem The item to enqueue.
     */
    public enqueue(queueItem: QueueItem): void {
        this.queue.push(queueItem);
        this.emit("push", queueItem);
        if (!this.busy) {
            this.next();
        }
    }

    /**
     * Stop playback and shutdown everything.
     */
    @destroy
    public stop(): void {
        this.stopped = true;
        this.mumbleStream.close();
        this.mumbleStream.end();
        if (this.ffmpeg) {
            try {
                this.ffmpeg.kill("1");
            } catch (err) {
                verbose("Killed ffmpeg process.");
            }
        }
        if (this.transcodeTimeout) {
            clearTimeout(this.transcodeTimeout);
        }
        this.clear();
        info("Output stopped.");
    }
}
