import { controller, route, ok, populate } from "hyrest";
import { component, inject } from "tsdi";
import { bind } from "decko";
import { Channel as MumbleChannel } from "mumble";
import { world } from "../scopes";
import { AudioOutput } from "../../server/audio-output";
import { Mumble } from "../../server/mumble";
import { MumbleUser } from "../models/mumble-user";

export interface ChannelTreeChannel {
    name: string;
    position: number;
    users: ChannelTreeUser[];
    children: ChannelTreeChannel[];
}

export interface ChannelTreeUser {
    name: string;
    id: number;
    session: number;
    selfMute: boolean;
    selfDeaf: boolean;
}

@controller
@component({ name: "Utilities" })
export class Utilities {
    @inject private readonly audioOutput!: AudioOutput;
    @inject private readonly mumble!: Mumble;

    /**
     * A recursive function which returns the sub-tree of the mumble server's channels
     * and users from the given channel.
     *
     * @param channel The channel to start the recursion from.
     *
     * @return The sub-tree below the given channel including that channel.
     */
    @bind private buildChannelTree(channel: MumbleChannel): ChannelTreeChannel {
        const { name, position } = channel;
        const users = channel.users.map((user) => ({
            name: user.name,
            id: user.id,
            session: user.session,
            selfMute: Boolean(user.selfMute),
            selfDeaf: Boolean(user.selfDeaf),
        }));
        const children = channel.children.sort((a, b) => a.position - b.position).map(this.buildChannelTree);
        return { name, position, users, children };
    }

    /**
     * Retrieves a nested structure of all channels and users in the mumble server.
     *
     * @return A tree with a channels and users in the mumble server.
     */
    @route("GET", "/channel-tree")
    public async channelTree(): Promise<ChannelTreeChannel> {
        return ok(this.buildChannelTree(this.mumble.rootChannel));
    }

    @route("POST", "/shut-up")
    public async shutUp(): Promise<{}> {
        this.audioOutput.clear();
        return ok();
    }

    /**
     * Returns a list of all registered users in the mumble server.
     *
     * @return A list of all registered users.
     */
    @(route("GET", "/mumble-users").dump(MumbleUser, world))
    public async getMumbleUsers(): Promise<MumbleUser[]> {
        const mumbleUsers = this.mumble.users().filter((user) => typeof user.id !== "undefined");
        return ok(mumbleUsers.map((user) => populate(world, MumbleUser, user)));
    }
}
