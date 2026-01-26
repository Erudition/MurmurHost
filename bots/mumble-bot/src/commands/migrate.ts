import { metadata, command, Command } from "clime";
import { TSDI, configure } from "tsdi";
import { setupWinston } from "../common/utils/winston";
import { ServerConfig } from "../config/server-config";
import { Database } from "../server/database";

export class MigrationApplication {
    // Components.
    @configure protected readonly database!: Database;

    @configure
    protected serverConfig(): ServerConfig {
        return this.config;
    }

    constructor(private config: ServerConfig) {}
}

setupWinston();
@command({ description: "Perform necessary database migrations" })
export default class MigrateCommand extends Command {
    // tslint:disable-line
    @metadata
    public async execute(config: ServerConfig): Promise<void> {
        if (!config.load()) {
            return;
        }
        // Always log queries when running migrations.
        config.dbLogging = true;
        const tsdi = new TSDI(new MigrationApplication(config));
        // Initialize database.
        const db = await tsdi.asyncGet(Database);
        // Execute migrations.
        await db.connection.runMigrations();
        tsdi.close();
    }
}
