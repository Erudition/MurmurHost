import { component, inject, destroy } from "tsdi";
import mkdirp from "mkdirp";
import { EventEmitter } from "events";
import { info } from "winston";
import { User as MumbleUser } from "mumble";
import { bind } from "decko";
import { VoiceInputUser } from "./user";
import { Mumble } from "../mumble";
import { Database } from "../database";
import { MumbleLink } from "../../common/models/mumble-link";
import { MumbleConnectionStatus } from "../../common/mumble-connection-status";
import { ServerConfig } from "../../config/server-config";
import { User } from "../../common/models/user";

/**
 * This class handles voice input for all users. It uses instances of user.js
 * and handles them.
 */
@component
export class AudioInput extends EventEmitter {
    @inject private readonly db!: Database;
    @inject private readonly config!: ServerConfig;
    @inject private readonly mumble!: Mumble;

    private users = new Map<number, VoiceInputUser>();

    private async reinitialize(): Promise<void> {
        this.mumble.on("user-connect", (user) => this.addUser(user));
        this.mumble.on("user-disconnect", this.removeUser);
        await Promise.all(this.mumble.users().map((user) => this.addUser(user)));
    }

    public async listen(): Promise<void> {
        mkdirp(this.config.tmpDir);
        this.mumble.on("status change", async ({ status }: { status: MumbleConnectionStatus }) => {
            if (status !== MumbleConnectionStatus.HEALTHY) {
                await Promise.all(this.mumble.users().map((user) => this.removeUser(user)));
            } else {
                await this.reinitialize();
            }
        });
        await this.reinitialize();
    }

    /**
     * Creates a local user object handling the data received from the mumble user of a registered user.
     * @param user The mumble user object.
     * @param databaseUser The user object from the database.
     */
    @bind public async addRegisteredUser(user: MumbleUser, databaseUser: User): Promise<void> {
        info(`Input registered for user ${user.name}`);
        const localUser = new VoiceInputUser(user, databaseUser);
        this.users.set(user.id, localUser);
        user.outputStream(true).pipe(localUser);
    }

    /**
     * Called when a user joined the server, or was there before the bot joined.
     * @param user The user who should be registered.
     */
    @bind private async addUser(user: MumbleUser): Promise<void> {
        const link = await this.db.getRepository(MumbleLink).findOne({
            where: { mumbleId: user.id },
            relations: ["user"],
        });
        if (!link) {
            return;
        }
        this.addRegisteredUser(user, link.user);
    }

    /**
     * Called when user disconnects. Unregisters the user.
     * @param user The user which disconnected.
     */
    @bind private removeUser(user: MumbleUser): void {
        const localUser = this.users[user.id];
        if (localUser) {
            this.users[user.id].stop();
            delete this.users[user.id];
        }
    }

    /**
     * Stop all timeouts and shutdown everything.
     */
    @destroy
    public stop(): void {
        this.users.forEach((user) => user.stop());
        info("Input stopped.");
    }
}
