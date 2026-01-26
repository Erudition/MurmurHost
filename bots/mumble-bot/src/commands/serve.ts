import { metadata, command, Command } from "clime";
import { TSDI } from "tsdi";
import { onKill } from "../common/utils/kill";
import { ServerConfig } from "../config/server-config";
import { RestApi } from "../server/api/rest-api";
import { AudioInput } from "../server/audio-input/audio-input";
import { ServerApplication } from "../server/server";
import { Telegram } from "../server/telegram/telegram";

@command({ description: "Start the API and the bot." })
export default class ServeCommand extends Command {
    @metadata
    public async execute(config: ServerConfig): Promise<void> {
        if (!config.load()) {
            return;
        }

        const tsdi = new TSDI(new ServerApplication(config));

        (await tsdi.asyncGet(RestApi)).listen();
        (await tsdi.asyncGet(AudioInput)).listen();
        (await tsdi.asyncGet(Telegram)).connect();

        onKill(() => tsdi.close());
    }
}
