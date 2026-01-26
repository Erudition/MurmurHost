import { observable, action, computed } from "mobx";
import { bind } from "decko";
import { subDays, addSeconds, areRangesOverlapping } from "date-fns";
import { component, inject } from "tsdi";
import { UsersStore } from "./users";
import { Cached } from "../../common/controllers/cached";
import { CachedAudio } from "../../common/models/cached-audio";
import { User } from "../../common/models/user";

@component
export class CachedAudioStore {
    @inject private readonly usersStore!: UsersStore;
    @inject private readonly cachedAudioController!: Cached;

    @observable private cachedAudios: Map<string, CachedAudio> = new Map();

    @observable public selectionStart: Date;
    @observable public selectionEnd: Date;

    @computed public get totalDuration(): number {
        return this.all.reduce((sum, cachedAudio) => sum + cachedAudio.duration, 0);
    }

    @computed public get selectionFollowing(): boolean {
        if (!this.selectionDefined) {
            return false;
        }
        if (this.selectionEnd.getTime() - this.newestTime > -5000) {
            return true;
        }
    }

    @computed public get selectionDefined(): boolean {
        return Boolean(this.selectionStart && this.selectionEnd);
    }

    @computed public get all(): CachedAudio[] {
        return Array.from(this.cachedAudios.values());
    }

    @computed public get newest(): CachedAudio {
        return this.all.reduce((newest, cachedAudio) => {
            if (!newest) {
                return cachedAudio;
            }
            if (addSeconds(cachedAudio.date, cachedAudio.duration) > addSeconds(newest.date, newest.duration)) {
                return cachedAudio;
            }
            return newest;
        }, undefined);
    }

    @computed public get oldest(): CachedAudio {
        return this.all.reduce((oldest, cachedAudio) => {
            if (!oldest || cachedAudio.date < oldest.date) {
                return cachedAudio;
            }
            return oldest;
        }, undefined);
    }

    @computed public get oldestTime(): number {
        const { oldest } = this;
        if (!oldest) {
            return subDays(new Date(), 1).getTime();
        }
        return this.oldest.date.getTime();
    }

    @computed public get newestTime(): number {
        const { newest } = this;
        if (!newest) {
            return Date.now();
        }
        return this.newest.date.getTime() + newest.duration * 1000;
    }

    @computed public get totalRange(): number {
        const { newestTime, oldestTime } = this;
        return newestTime - oldestTime;
    }

    @computed public get selectedRange(): number {
        const { selectionStart, selectionEnd } = this;
        return selectionEnd.getTime() - selectionStart.getTime();
    }

    @computed public get amplitudeTotalMin(): number {
        return this.all
            .map((cachedAudio) => cachedAudio.amplitude)
            .reduce((result, current) => Math.min(result, current));
    }

    @computed public get amplitudeTotalMax(): number {
        return this.all
            .map((cachedAudio) => cachedAudio.amplitude)
            .reduce((result, current) => Math.max(result, current));
    }

    @computed public get amplitudeTotalRange(): number {
        return this.amplitudeTotalMax - this.amplitudeTotalMin;
    }

    public byUser(user: User): CachedAudio[] {
        return this.all.filter((cachedAudio) => cachedAudio.user.id === user.id);
    }

    @bind public isInSelection({ date: start, duration }: CachedAudio): boolean {
        const { selectionStart, selectionEnd } = this;
        if (!selectionStart || !selectionEnd) {
            return false;
        }
        const end = addSeconds(start, duration);
        if (selectionStart > selectionEnd) {
            return areRangesOverlapping(start, end, selectionEnd, selectionStart);
        }
        return areRangesOverlapping(start, end, selectionStart, selectionEnd);
    }

    @computed public get inSelection(): CachedAudio[] {
        return this.all.filter(this.isInSelection);
    }

    public inSelectionByUser(user: User): CachedAudio[] {
        return this.inSelection.filter((cachedAudio) => cachedAudio.user.id === user.id);
    }

    @bind @action public add(cachedAudio: CachedAudio): void {
        const { selectionFollowing } = this;
        cachedAudio.user = this.usersStore.byId(cachedAudio.user.id);
        if (selectionFollowing) {
            const distance = addSeconds(cachedAudio.date, cachedAudio.duration).getTime() - this.newestTime;
            this.selectionEnd = addSeconds(this.selectionEnd, distance / 1000);
            this.selectionStart = addSeconds(this.selectionStart, distance / 1000);
        }
        this.cachedAudios.set(cachedAudio.id, cachedAudio);
    }

    @bind @action public remove({ id }: CachedAudio): void {
        if (!this.cachedAudios.has(id)) {
            return;
        }
        this.cachedAudios.delete(id);
    }

    @bind @action public async delete({ id }: CachedAudio): Promise<void> {
        await this.cachedAudioController.deleteCached(id);
        this.cachedAudios.delete(id);
    }
}
