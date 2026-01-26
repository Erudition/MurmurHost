import { Channel } from "mumble";
/* eslint-disable @typescript-eslint/no-explicit-any */
import { PassThrough } from "stream";

function mockUser(user: any): any {
    user.outputStream = () => new PassThrough();
    return user;
}

const userStrangerOne = mockUser({
    id: 4,
    name: "Stranger one",
    session: 84,
});

const userStrangerTwo = mockUser({
    id: 7,
    name: "Stranger two",
    session: 171,
});

const userStrangerThree = mockUser({
    id: 23,
    name: "Stranger three",
    session: 2134,
});

const userUnregistered = mockUser({
    name: "Unregistered Stranger",
    session: 2134,
});

const channelSubchild1: Channel = {
    id: 3,
    name: "Subchild 1",
    position: 0,
    children: [],
    users: [userStrangerOne, userStrangerTwo],
    links: [],
    addSubChannel: jest.fn(),
    getPermissions: jest.fn(),
    join: jest.fn(),
    remove: jest.fn(),
    sendMessage: jest.fn(),
};

const channelChild1: Channel = {
    id: 1,
    name: "Child 1",
    position: 0,
    children: [channelSubchild1],
    users: [],
    links: [],
    addSubChannel: jest.fn(),
    getPermissions: jest.fn(),
    join: jest.fn(),
    remove: jest.fn(),
    sendMessage: jest.fn(),
};

const channelChild2 = {
    id: 2,
    name: "Child 2",
    position: 1,
    children: [],
    users: [userStrangerThree],
    links: [],
    addSubChannel: jest.fn(),
    getPermissions: jest.fn(),
    join: jest.fn(),
    remove: jest.fn(),
    sendMessage: jest.fn(),
};

const channelRoot: Channel = {
    id: 0,
    name: "Root",
    position: 0,
    children: [channelChild1, channelChild2],
    users: [userUnregistered],
    links: [],
    addSubChannel: jest.fn(),
    getPermissions: jest.fn(),
    join: jest.fn(),
    remove: jest.fn(),
    sendMessage: jest.fn(),
};

export class MockMumbleConnection {
    private disconnectCallback: () => void;
    public mockInput = new PassThrough();
    public mockOutput = new PassThrough();

    constructor() {
        (this.mockInput as any).close = () => this.mockInput.destroy();
        (this.mockOutput as any).close = () => this.mockInput.destroy();
    }

    public mockUsers = [userStrangerOne, userStrangerTwo, userStrangerThree, userUnregistered];

    public mockChannels = [channelRoot, channelChild1, channelChild2, channelSubchild1];

    public on(eventName: string, callback): void {
        if (eventName === "ready") {
            setTimeout(callback, 5);
            return;
        }
        if (eventName === "disconnect") {
            this.disconnectCallback = callback;
        }
    }

    public disconnect(): void {
        this.inputStream().end();
        this.outputStream().end();
        if (this.disconnectCallback) {
            this.disconnectCallback();
        }
    }

    public users(): any[] {
        return [...this.mockUsers];
    }

    public channel(): { id: number; name: string; position: number; children: any[]; users: any[] }[] {
        return [...this.mockChannels];
    }

    public authenticate(): void {
        return;
    }

    public get rootChannel(): Channel {
        return channelRoot;
    }

    public userById(id: number): any {
        return this.mockUsers.find((user) => (user as any).id === id);
    }

    public inputStream(): any {
        return this.mockInput;
    }

    public outputStream(): any {
        return this.mockOutput;
    }
}

export function connect(url, options, callback): void {
    callback(undefined, new MockMumbleConnection());
}
