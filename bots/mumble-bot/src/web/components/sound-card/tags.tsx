import * as React from "react";
import { observer } from "mobx-react";
import { action, observable, computed } from "mobx";
import { bind } from "decko";
import { external, inject } from "tsdi";
import { Icon, Label, Dropdown, DropdownItemProps } from "semantic-ui-react";
import * as css from "./sound-card.scss";
import classNames from "classnames/bind";
import { Sound } from "../../../common/models/sound";
import { Tag } from "../../../common/models/tag";
import { SoundsStore } from "../../store/sounds";
import { TagsStore } from "../../store/tags";
import { TagLabel } from "../tag-label/tag-label";

const cx = classNames.bind(css);

export interface TagsProps {
    sound: Sound;
}

@observer
@external
export class SoundCardTags extends React.Component<TagsProps> {
    @inject private readonly sounds!: SoundsStore;
    @inject private readonly tags!: TagsStore;

    @observable private editTags = false;
    @observable private tagsLoading = false;

    @bind @action private async handleUntag(tag: Tag): Promise<void> {
        await this.sounds.untag(this.props.sound, tag);
    }

    @bind @action private handleStartEditTags(): void {
        this.editTags = true;
    }

    @bind @action private handleFinishEditTags(): void {
        this.editTags = false;
    }

    @bind @action private async handleAddTagChange(
        _: React.SyntheticInputEvent,
        { value }: { value: string },
    ): Promise<void> {
        this.tagsLoading = true;
        await this.sounds.tag(this.props.sound, value);
        this.tagsLoading = false;
    }

    @computed private get tagList(): Tag[] {
        return this.props.sound.soundTagRelations.map((relation) => relation.tag);
    }

    @computed private get dropdownOptions(): DropdownItemProps[] {
        return this.tags.dropdownOptions.filter((option) => {
            return !this.props.sound.soundTagRelations.some((relation) => relation.tag.id === option.value);
        });
    }

    public render(): JSX.Element {
        return (
            <div className={css.tags}>
                <Label.Group className={css.tagGroup}>
                    {this.tagList.map((tag) => (
                        <TagLabel key={tag.id} tag={tag} onRemove={this.editTags && (() => this.handleUntag(tag))} />
                    ))}
                    {!this.editTags ? (
                        <Icon.Group className={cx({ addTags: true, notEmpty: this.tagList.length > 0 })}>
                            <Icon className={css.tag} name="tag" color="grey" link onClick={this.handleStartEditTags} />
                            <Icon
                                name="pencil"
                                corner="bottom right"
                                color="grey"
                                link
                                onClick={this.handleStartEditTags}
                            />
                        </Icon.Group>
                    ) : (
                        <Icon name="checkmark" color="grey" link onClick={this.handleFinishEditTags} />
                    )}
                </Label.Group>
                {this.editTags && (
                    <>
                        <Dropdown
                            placeholder="Add Tag"
                            search
                            fluid
                            selection
                            selectOnNavigation={false}
                            selectOnBlur={false}
                            options={this.dropdownOptions}
                            onChange={this.handleAddTagChange}
                            loading={this.tagsLoading}
                            disabled={this.tagsLoading}
                            value={undefined}
                            closeOnChange={false}
                            allowAdditions
                            className={css.select}
                        />{" "}
                    </>
                )}
            </div>
        );
    }
}
