import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, initialize, inject } from "tsdi";
import { DropdownItemProps } from "semantic-ui-react";
import { Tag } from "../../common/models/tag";
import { Tags } from "../../common/controllers/tags";
import { LoginStore } from "./login";

@component
export class TagsStore {
    @inject private readonly tagsController!: Tags;
    @inject private readonly loginStore!: LoginStore;

    @observable private tags = new Map<string, Tag>();

    @initialize
    protected async initialize(): Promise<void> {
        await this.loginStore.onLogin$.toPromise();
        const tags = await this.tagsController.listTags();
        tags.forEach((tag) => this.tags.set(tag.id, tag));
    }

    @computed public get all(): Tag[] {
        return Array.from(this.tags.values());
    }

    @bind public byId(id: string): Tag {
        return this.tags.get(id);
    }

    @bind @action public async createTag(name: string): Promise<Tag> {
        const newTag = await this.tagsController.createTag({ name });
        this.tags.set(newTag.id, newTag);
        return newTag;
    }

    @computed public get dropdownOptions(): DropdownItemProps[] {
        return this.all.map((tag) => ({
            key: tag.id,
            value: tag.id,
            text: tag.name,
        }));
    }
}
