/* eslint-disable @typescript-eslint/no-explicit-any */
process.env.NTBA_FIX_319 = "true";

import * as path from "path";
import * as uuid from "uuid";
import { TSDI } from "tsdi";
import * as Winston from "winston";
import { ServerConfig } from "../src/config/server-config";

process.on("unhandledRejection", (err: Error) => {
    console.error(`Unhandled Promise rejection: ${err && err.message}`);
    console.error(err);
});
process.on("uncaughtException", (err: Error) => {
    console.error(`Unhandled Promise rejection: ${err && err.message}`);
    console.error(err);
});

declare namespace global {
    let tsdi: TSDI;
}
declare let tsdi: TSDI;

// Setup winston.
if (!process.env["DEBUG"]) {
    Winston.remove(Winston.transports.Console);
    Winston.add(
        new Winston.transports.Console({
            format: Winston.format.combine(
                Winston.format.timestamp({ format: "YYYY-MM-DDTHH:mm:ss" }),
                Winston.format.colorize(),
                Winston.format.printf((info) => `${info.timestamp} - ${info.level}: ${info.message}`),
            ),
            level: "error",
        }),
    ).silent = true;
}

// Mock modules.
jest.mock("mumble");
jest.mock("youtube-dl");
jest.mock("../src/visualizer/executor");

import { ServerApplication } from "../src/server/server";
import { RestApi } from "../src/server/api/rest-api";
import { AudioOutput } from "../src/server/audio-output";

// Mock the `baseUrl` provided by `config.js`.
(global as any).baseUrl = "example.com";

beforeEach(async () => {
    const config = new ServerConfig();
    const baseTmpDir = path.join("/", "tmp", `bot-${uuid.v4()}`);
    Object.assign(config, {
        port: 23279,
        url: "localhost",
        audioCacheAmount: 100,
        dbName: process.env["POSTGRES_DB"] || "bot-test",
        dbUsername: process.env["POSTGRES_USER"],
        dbPassword: process.env["POSTGRES_PASSWORD"],
        dbHost: process.env["POSTGRES_HOST"] || "localhost",
        dbLogging: Boolean(process.env["DEBUG"]),
        tmpDir: path.join(baseTmpDir, "tmp"),
        soundsDir: path.join(baseTmpDir, "sound"),
        name: "test-bot",
    });
    config.load();
    global.tsdi = new TSDI(new ServerApplication(config));
    await tsdi.asyncGet(RestApi);
    await tsdi.asyncGet(AudioOutput);
});

afterEach(async () => {
    tsdi.close();
});

jest.setTimeout(30000);
