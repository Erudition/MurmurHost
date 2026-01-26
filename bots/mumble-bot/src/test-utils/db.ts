import { Database } from "../server/database";

export async function startDb(): Promise<void> {
    const db = await tsdi.asyncGet(Database);
    await db.connection.query(`
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    `);
    await db.connection.runMigrations();
}

export async function stopDb(): Promise<void> {
    const db = await tsdi.asyncGet(Database);
    // This needs to be performed in order to flush all active queries.
    // There might be queries ongoing which, on termination will fail all tests.
    // By executing this dummy query it is ensured that the database driver waits for
    // all queries before closing.
    await db.connection.query("SELECT 1");
}
