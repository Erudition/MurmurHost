import { component, inject, destroy, initialize } from "tsdi";
import { Connection, connect } from "mumble";
import { info, error, warn, debug } from "winston";
import { bind } from "decko";
import { EventEmitter } from "events";
import { MumbleConnectionStatus } from "../common/mumble-connection-status";
import { ServerConfig } from "../config/server-config";

@component
export class Mumble extends EventEmitter {
    @inject private readonly config!: ServerConfig;

    public connection: Connection;
    public status = MumbleConnectionStatus.CONNECTING;

    private terminated = false;
    private reconnectTimeout: ReturnType<typeof setTimeout>;

    @bind private setStatus(status: MumbleConnectionStatus): void {
        this.status = status;
        this.emit("status change", { status });
    }

    @bind private reconnect(): void {
        if (this.terminated) {
            return;
        }
        if (this.reconnectTimeout) {
            debug("Disconnected while being disconnected. Odd...");
            return;
        }
        info(`Disconnected from server. ` + `Attempting to reconnect in ${this.config.reconnectTimeout} seconds.`);
        this.reconnectTimeout = setTimeout(() => {
            this.reconnectTimeout = undefined;
            debug("Reconnecting...");
            this.connect();
        }, this.config.reconnectTimeout * 1000);
    }

    @initialize
    protected async connect(): Promise<void> {
        const { keyContent, certContent, url, name, mumblePassword } = this.config;
        if (!keyContent || !certContent) {
            warn("Connecting to mumble without SSL. Connection will be unsecured, bot will not be able to register!");
        }
        try {
            this.setStatus(MumbleConnectionStatus.CONNECTING);
            this.connection = await new Promise<Connection>((resolve, reject) => {
                connect(`mumble://${url}`, { key: keyContent, cert: certContent }, (err, connection) => {
                    if (err) {
                        return reject(err);
                    }
                    connection.on("error", (data) => {
                        this.setStatus(MumbleConnectionStatus.ERROR);
                        error("An error with the mumble connection has occured:", data);
                        this.reconnect();
                    });
                    connection.authenticate(name, mumblePassword);
                    connection.on("ready", () => resolve(connection));
                    connection.on("disconnect", () => {
                        this.setStatus(MumbleConnectionStatus.DISCONNECTED);
                        this.reconnect();
                    });
                });
            });
            info("Connected to mumble.");
            this.setStatus(MumbleConnectionStatus.HEALTHY);
        } catch (err) {
            error(`Mumble connection terminated with error: ${err.message}`, err);
            this.reconnect();
        }
    }

    @destroy
    public stop(): Promise<undefined> {
        this.terminated = true;
        return new Promise((resolve) => {
            if (!this.connection) {
                return;
            }
            this.connection.on("disconnect", () => {
                info("Disconnected from mumble.");
                resolve();
            });
            this.connection.disconnect();
        });
    }

    public get userById(): Connection["userById"] {
        return this.connection.userById.bind(this.connection);
    }

    public get users(): Connection["users"] {
        return this.connection.users.bind(this.connection);
    }

    public get inputStream(): Connection["inputStream"] {
        return this.connection.inputStream.bind(this.connection);
    }

    public get rootChannel(): Connection["rootChannel"] {
        return this.connection.rootChannel;
    }

    public get user(): Connection["user"] {
        return this.connection.user;
    }
}
