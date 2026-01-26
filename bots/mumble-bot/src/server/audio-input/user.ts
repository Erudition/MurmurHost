import { error, info, verbose } from "winston";
import * as uuid from "uuid";
import { bind } from "decko";
import FFMpeg, { FfmpegCommand } from "fluent-ffmpeg";
import * as Stream from "stream";
import { PassThrough as PassThroughStream } from "stream";
import { external, inject, initialize } from "tsdi";
import { User as MumbleUser, User } from "mumble";
import { CachedAudio } from "../../common/models/cached-audio";
import { ServerConfig } from "../../config/server-config";
import { AudioCache } from "../audio-cache";

const TIMEOUT_THRESHOLD = 300;
const audioFreq = 48000;
const lowPassAlpha = 0.001;

function toDecibel(input: number): number {
    return 20 * Math.log10(input);
}

/**
 * This class belongs to the VoiceInput and handles the speech recognition for a
 * single user.
 */
@external
export class VoiceInputUser extends Stream.Writable {
    @inject private readonly config!: ServerConfig;
    @inject private readonly cache!: AudioCache;

    private user: MumbleUser;
    private databaseUser: User;
    private speaking = false;
    private passthrough: PassThroughStream;
    private timeout: NodeJS.Timer;
    private speakStartTime: Date;
    private currentId: string;
    private encoder: FfmpegCommand;

    private amplitudeSamples = 0;
    private amplitudeSum = 0;
    private lowPassCache = 0;

    /**
     * @constructor
     * @param user Mumble user to recognize the speech of.
     * @param databaseUser The user from the database.
     */
    constructor(user, databaseUser) {
        super();
        this.user = user;
        this.databaseUser = databaseUser;
    }

    @initialize
    protected initialize(): void {
        this.createNewRecordingFile();
    }

    /**
     * Feed raw PCM audio data captured from mumble to this user.
     * @param chunk Buffer of raw PCM audio data.
     * @param encoding unused.
     * @param done callback.
     */
    public _write(chunk: Buffer, encoding?: string, done?: Function): boolean {
        if (!this.speaking) {
            this.speechStarted();
        }
        this.speechContinued(chunk);
        done();
        return true;
    }

    /**
     * Refreshes the timeout of silence after which the audio will be sliced into different records.
     * @returns {undefined}
     */
    private refreshTimeout(): void {
        if (this.timeout) {
            clearTimeout(this.timeout);
        }
        this.timeout = global.setTimeout(this.speechStopped.bind(this), TIMEOUT_THRESHOLD);
    }

    /**
     * When user started speaking.
     */
    private speechStarted(): void {
        this.speaking = true;
        this.speakStartTime = new Date();
    }

    @bind private handleEncoderError(_err: Error): void {
        error(`Encoder for user ${this.user.name} crashed.`);
    }

    /**
     * Creates a new temporary record file.
     */
    private createNewRecordingFile = (): void => {
        this.currentId = uuid.v4();
        this.passthrough = new PassThroughStream();
        this.encoder = FFMpeg(this.passthrough)
            .inputOptions("-f", "s16le", "-ar", String(audioFreq), "-ac", "1")
            .on("error", this.handleEncoderError)
            .audioCodec("libmp3lame")
            .format("mp3")
            .save(`${this.config.tmpDir}/${this.currentId}`);
    };

    /**
     * When user stopped speaking.
     */
    private speechStopped(): void {
        this.speaking = false;
        this.passthrough.end();
        const cachedAudio = Object.assign(new CachedAudio(), {
            id: this.currentId,
            user: this.databaseUser,
            duration: (Date.now() - this.speakStartTime.getTime()) / 1000,
            date: new Date(),
            amplitude: toDecibel(this.amplitudeSum / this.amplitudeSamples),
        });
        this.cache.add(cachedAudio);
        this.createNewRecordingFile();
        this.amplitudeSum = 0;
        this.amplitudeSamples = 0;
        this.lowPassCache = 0;
    }

    /**
     * When user continues speaking this method will be called,
     * the audio will be encoded and the timeout will be refreshed.
     * @param chunk - The user's speech buffer.
     */
    private speechContinued(chunk: Buffer): void {
        this.amplitudeSamples += chunk.length;
        for (let i = 0; i < chunk.length; ++i) {
            const value = Math.abs(chunk[i]);
            const amplitude = lowPassAlpha * value + (1.0 - lowPassAlpha) * this.lowPassCache;
            this.lowPassCache = value;
            this.amplitudeSum += amplitude;
        }
        this.passthrough.write(chunk);
        this.refreshTimeout();
    }

    /**
     * Stop all timeouts and shutdown everything.
     */
    public stop(): void {
        this.passthrough.end();
        // Ignore error when killing encoder.
        this.encoder.removeListener("error", this.handleEncoderError);
        this.encoder.once("error", () => {
            return;
        });
        try {
            this.encoder.kill("1");
        } catch (err) {
            verbose("Killed ffmpeg process.");
        }
        if (this.timeout) {
            clearTimeout(this.timeout);
        }
        info(`Input stopped for user ${this.user.name}`);
    }
}
