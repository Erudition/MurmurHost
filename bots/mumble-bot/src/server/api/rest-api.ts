import Express from "express";
import { Socket } from "net";
import { Request, Response } from "express";
import expressWS from "express-ws";
import * as BodyParser from "body-parser";
import { Server } from "http";
import { component, inject, initialize, TSDI, destroy, Constructable } from "tsdi";
import { info, error } from "winston";
import { bind } from "decko";
import { createReadStream, existsSync } from "fs";
import { hyrest } from "hyrest-express";
import { AuthorizationMode, configureController, ControllerMode } from "hyrest";
import morgan from "morgan";
import { AudioCache } from "../audio-cache";
import { cors, catchError } from "./middlewares";
import { createLiveWebsocket } from "./live-websocket";
import Ffmpeg from "fluent-ffmpeg";
import { extname } from "path";
import { Database } from "../database";
import { allControllers } from "../../common/controllers/all-controllers";
import { Sound } from "../../common/models/sound";
import { Token } from "../../common/models/token";
import { getAuthTokenId } from "../../common/utils/authorization";
import { ServerConfig } from "../../config/server-config";
import { Context } from "../../common/context";

@component
export class RestApi {
    @inject private readonly db!: Database;
    @inject private readonly config!: ServerConfig;
    @inject private readonly audioCache!: AudioCache;
    @inject private readonly tsdi!: TSDI;

    private connections = new Set<Socket>();
    public app: Express.Application;
    private server: Server;

    @initialize
    protected initialize(): void {
        configureController(allControllers, { mode: ControllerMode.SERVER });
        this.app = Express();
        this.app.use(BodyParser.json({ limit: "100mb", strict: false }));
        this.app.use(BodyParser.urlencoded({ limit: "100mb", extended: true }));
        this.app.use(morgan("tiny", { stream: { write: (msg) => info(msg.trim()) } }));
        this.app.use(cors);
        this.app.use(catchError);
        this.app.get("/cached/:id/download", this.downloadCached);
        this.app.get("/cached/:id/visualized", this.downloadVisualizedCached);
        this.app.get("/sound/:id/download", this.downloadSoundSimple);
        this.app.get("/sound/:id/download/:fileName", this.downloadSoundWithFilename);
        this.app.get("/sound/:id/visualized", this.downloadVisualizedSound);
        expressWS(this.app).app.ws("/live", this.websocket);
        this.app.use(
            hyrest(...allControllers.map((controller: Constructable<unknown>) => this.tsdi.get(controller)))
                .context((req) => new Context(req))
                .defaultAuthorizationMode(AuthorizationMode.AUTH)
                .authorization(async (req) => {
                    const id = getAuthTokenId(req);
                    if (!id) {
                        return false;
                    }
                    const token = await this.db.getRepository(Token).findOne({
                        where: { id },
                        relations: ["user"],
                    });
                    if (!token) {
                        return false;
                    }
                    if (token.deleted) {
                        return false;
                    }
                    if (!token.user.enabled) {
                        return false;
                    }
                    return true;
                }),
        );
    }

    public listen(): void {
        const { port } = this.config;
        this.server = this.app.listen(port);
        this.server.on("connection", this.onConnection);
        info(`Api started, listening on port ${port}.`);
    }

    /**
     * Called when a new connection was opened by the webserver.
     * @param conn The socket that was opened.
     */
    @bind private onConnection(conn: Socket): void {
        this.connections.add(conn);
        conn.on("close", () => this.connections.delete(conn));
    }

    /**
     * Stop the api immediatly.
     * @return Promise which will be resolved when the website has been shut down.
     */
    @destroy
    public stop(): Promise<void> {
        return new Promise((resolve) => {
            if (!this.server) {
                return;
            }
            this.server.close(() => {
                info(`Terminating ${this.connections.size} open websocket connections.`);
                for (const socket of this.connections) {
                    socket.destroy();
                    this.connections.delete(socket);
                }
                info("Api stopped.");
                resolve();
            });
        });
    }

    @bind public websocket(ws): void {
        createLiveWebsocket(ws);
    }

    @bind public downloadCached({ params }: Request, res: Response): Response {
        const { id } = params;
        const sound = this.audioCache.byId(id);
        if (!sound) {
            return res.status(404).send();
        }

        res.setHeader("Content-disposition", `attachment; filename=cached_${id}.mp3`);
        try {
            createReadStream(`${this.config.tmpDir}/${sound.id}`)
                .on("error", (err) => {
                    if (err.code === "ENOENT") {
                        return res.status(404).send();
                    }
                    error(`Error occured when trying to read cached record with id ${id}`);
                })
                .pipe(res);
        } catch (err) {
            error(`Error occured when trying to open read stream: ${err.message}`);
        }
    }

    @bind public async downloadVisualizedCached({ params }: Request, res: Response): Promise<Response> {
        const { id } = params;
        const sound = this.audioCache.byId(id);
        if (!sound) {
            return res.status(404).send();
        }

        const fileName = `${this.config.tmpDir}/${sound.id}.png`;
        const trySend = async (retries = 0): Promise<Response | undefined> => {
            if (!existsSync(fileName)) {
                if (retries === 5) {
                    return res.status(404).send();
                }
                setTimeout(() => trySend(retries + 1), 500);
                return;
            }
            try {
                res.status(200);
                createReadStream(fileName)
                    .on("error", (err) => {
                        res.status(500).send();
                        error(`Error sending visualization of ${sound.id} to client.`, err);
                    })
                    .pipe(res);
            } catch (err) {
                error("Error occured during request of sound visualization.", err);
                return res.status(500).send();
            }
        };

        await trySend();
    }

    @bind private async downloadSound(
        id: string,
        response: Response,
        format: "mp3" | "ogg" = "mp3",
        resultFileName?: string,
    ): Promise<void> {
        const sound = await this.db.getRepository(Sound).findOne(id);
        if (!sound) {
            response.status(404).send();
        }

        const fileName = `${this.config.soundsDir}/${sound.id}`;
        if (!existsSync(fileName)) {
            error(`Missing audio file for sound ${sound.id}.`);
            response.status(404).send();
            return;
        }

        const attachmentName =
            resultFileName ?? `${sound.description.toLowerCase().replace(/[^a-z0-9]/gi, "-")}.${format}`;
        response.setHeader("Content-disposition", `attachment; filename=${attachmentName}`);
        response.status(200);
        try {
            switch (format) {
                case "ogg":
                    response.setHeader("content-type", "audio/ogg");
                    Ffmpeg(fileName)
                        .audioCodec("libopus")
                        .format("ogg")
                        .once("error", (err) => {
                            error(`Error recording file ${fileName} to ogg.`, err);
                            return response.status(500).send();
                        })
                        .stream(response);
                    break;
                case "mp3":
                    response.setHeader("content-type", "audio/mp3");
                    createReadStream(fileName)
                        .on("error", (err) => {
                            error(`Error sending audio file ${fileName} to client.`, err);
                            response.status(500).send();
                        })
                        .pipe(response);
                    break;
                default:
                    response.status(400).send({ error: "Invalid format." });
            }
        } catch (err) {
            error("Error occured during request of sound download.", err);
            response.status(500).send();
        }
    }

    @bind public downloadSoundWithFilename({ params }: Request, res: Response): Response {
        const { id, fileName } = params;
        const format = extname(fileName).replace(/\./, "").toLowerCase();
        if (format !== "ogg" && format !== "mp3") {
            res.status(400).send({ error: "Invalid format." });
            return;
        }
        this.downloadSound(id, res, format, fileName);
    }

    @bind public downloadSoundSimple({ params, query }: Request, res: Response): Response {
        this.downloadSound(params.id, res, query.format ?? "mp3");
        return res;
    }

    @bind public async downloadVisualizedSound({ params }: Request, res: Response): Promise<Response> {
        const { id } = params;
        const sound = await this.db.getRepository(Sound).findOne(id);
        if (!sound) {
            return res.status(404).send();
        }

        const fileName = `${this.config.soundsDir}/${sound.id}.png`;
        if (!existsSync(fileName)) {
            error(`Missing visalization file ${fileName} for sound ${sound.id}.`);
            res.status(404).send();
            return;
        }
        try {
            res.status(200);
            createReadStream(fileName)
                .on("error", (err) => {
                    error(`Error sending visualization of ${fileName} to client.`, err);
                    res.status(500).send();
                })
                .pipe(res);
        } catch (err) {
            error("Error occured during request of sound visualization.", err);
            return res.status(500).send();
        }
    }
}
