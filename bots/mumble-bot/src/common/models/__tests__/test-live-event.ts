import { CachedAudio } from "../cached-audio";
import { LiveEvent } from "../live-event";
import { QueueItem } from "../queue-item";

describe("LiveEvent model", () => {
    it.each([
        ["cache add", { id: "some-id" } as CachedAudio],
        ["cache remove", { id: "some-id" } as CachedAudio],
        ["queue shift", { type: "sound" } as QueueItem],
        ["queue push", { type: "sound" } as QueueItem],
        ["queue clear"],
        [
            "init",
            [{ type: "sound" }, { type: "sound" }] as QueueItem[],
            [{ id: "some-id-1" }, { id: "some-id-2" }] as CachedAudio[],
        ],
        [],
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ])(`constructs the expected object with arguments %s"`, (...args: any[]) => {
        expect(new LiveEvent(args[0], args[1], args[3])).toMatchSnapshot();
    });
});
