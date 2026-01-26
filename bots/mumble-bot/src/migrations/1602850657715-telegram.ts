import { MigrationInterface, QueryRunner } from "typeorm";
import { info } from "winston";

export class Telegram1602850657715 implements MigrationInterface {
    public async up(queryRunner: QueryRunner): Promise<void> {
        info("Applying migration: Telegram");
        await queryRunner.query(`
            CREATE TABLE "telegram_user" (
                "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
                "userId" uuid,
                "telegramName" character varying(100) NOT NULL,
                CONSTRAINT "PK_telegram_user"
                PRIMARY KEY ("id")
            )
        `);
        await queryRunner.query(`
            ALTER TABLE "telegram_user"
            ADD CONSTRAINT "FK_telegram_user_user"
            FOREIGN KEY ("userId")
            REFERENCES "user"("id")
        `);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        info("Reverting migration: Telegram");
        await queryRunner.query(`ALTER TABLE "telegram_user" DROP CONSTRAINT "FK_telegram_user_user"`);
        await queryRunner.query(`DROP TABLE "telegram_user"`);
    }
}
