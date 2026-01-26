process.env.NTBA_FIX_319 = "true";

import { CLI, Shim } from "clime";
import { error } from "winston";
import { setupWinston } from "./common/utils/winston";

setupWinston();

process.on("unhandledRejection", (err: Error) => {
    error(`Unhandled Promise rejection: ${err.message}`);
    console.error(err);
});
process.on("uncaughtException", (err: Error) => {
    error(`Unhandled Promise rejection: ${err.message}`);
    console.error(err);
});

const cli = new CLI("bot", `${__dirname}/commands`);
const shim = new Shim(cli);
shim.execute(process.argv);
