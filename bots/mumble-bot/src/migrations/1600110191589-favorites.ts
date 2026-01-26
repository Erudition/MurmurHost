import { MigrationInterface, QueryRunner } from "typeorm";
import { info } from "winston";

export class Favorites1600110191589 implements MigrationInterface {
    public async up(queryRunner: QueryRunner): Promise<void> {
        info("Applying migration: Favorites");
        await queryRunner.query(`
            CREATE TABLE "favorite" (
                "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
                "userId" uuid,
                "soundId" uuid,
                CONSTRAINT "PK_favorites"
                PRIMARY KEY ("id")
            )
        `);
        await queryRunner.query(`
            ALTER TABLE "favorite"
            ADD CONSTRAINT "FK_favorite_user"
            FOREIGN KEY ("userId")
            REFERENCES "user"("id")
        `);
        await queryRunner.query(`
            ALTER TABLE "favorite"
            ADD CONSTRAINT "FK_favorite_sound"
            FOREIGN KEY ("soundId")
            REFERENCES "sound"("id")
        `);
    }

    public async down(queryRunner: QueryRunner): Promise<void> {
        info("Reverting migration: Favorites");
        await queryRunner.query(`ALTER TABLE "favorite" DROP CONSTRAINT "FK_favorite_user"`);
        await queryRunner.query(`ALTER TABLE "favorite" DROP CONSTRAINT "FK_favorite_sound"`);
        await queryRunner.query(`DROP TABLE "favorites"`);
    }
}
