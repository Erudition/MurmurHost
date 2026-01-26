import { Message } from "node-telegram-bot-api";

export interface TelegramCommand {
    /** The command to register, without leading slash ("users" instead of "/users"). */
    command: string;
    /** A textual description used for explaining the command in telegram. */
    description: string;
    /** A callback that will be invoked with a message once the command has been received. */
    onMessage: (msg: Message) => void;
}

export enum CallbackDataType {
    FAVORITE = 0,
    STALK = 1,
    USERS = 2,
}

export type CallbackQueryData =
    | [CallbackDataType.FAVORITE, string]
    | [CallbackDataType.STALK, number]
    | [CallbackDataType.USERS];
