import * as uuid from "uuid";
import { component, inject, destroy, initialize } from "tsdi";
import { createConnection, Connection } from "typeorm";
import { info, error } from "winston";
import { migrations } from "../migrations";
import { allDatabaseModels } from "../common/models/all-models";
import { ServerConfig } from "../config/server-config";

@component
export class Database {
    @inject private readonly config!: ServerConfig;

    public connection!: Connection;

    @initialize
    protected async connect(): Promise<void> {
        this.connection = await createConnection({
            name: uuid.v4(),
            entities: allDatabaseModels,
            database: this.config.dbName,
            type: this.config.dbDriver,
            logging: this.config.dbLogging,
            password: this.config.dbPassword,
            port: this.config.dbPort,
            username: this.config.dbUsername,
            host: this.config.dbHost,
            extra: { ssl: this.config.dbSSL },
            migrations,
        });
        info("Connected to database.");
    }

    public get getRepository(): Connection["getRepository"] {
        return this.connection.getRepository.bind(this.connection);
    }

    public get createQueryBuilder(): Connection["createQueryBuilder"] {
        return this.connection.createQueryBuilder.bind(this.connection);
    }

    @destroy
    protected async stop(): Promise<void> {
        if (this.connection && this.connection.isConnected) {
            try {
                await this.connection.close();
            } catch (err) {
                error(`Error occured when closing databsae connection: ${err.message}`);
            }
            info("Disconnected from database.");
        }
    }
}
