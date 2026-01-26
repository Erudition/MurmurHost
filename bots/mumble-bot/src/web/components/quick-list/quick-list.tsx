import * as React from "react";
import classNames from "classnames";
import { external, inject } from "tsdi";
import { observer } from "mobx-react";
import { bind } from "decko";
import { observable, computed, action } from "mobx";
import { Input, Menu, Dropdown, Label, Icon } from "semantic-ui-react";
import * as css from "./quick-list.scss";
import { PlaylistsStore } from "../../store/playlists";

@observer
@external
export class QuickList extends React.Component {
    @inject private readonly playlists!: PlaylistsStore;

    @observable private loading = false;
    @observable private description = "";
    @observable private open = false;

    @computed private get visible(): boolean {
        return this.playlists.quickList.length > 0;
    }

    @computed private get descriptionPlaceholder(): string {
        return `Playlist from ${new Date().toLocaleString()}`;
    }

    @computed private get dropdownText(): string {
        const { quickList } = this.playlists;
        if (quickList.length === 1) {
            return `1 item`;
        }
        return `${quickList.length} items`;
    }

    @bind @action public async handlePlay(): Promise<void> {
        this.loading = true;
        await this.playlists.playQuickList();
        this.loading = false;
    }

    @bind @action public async handleClear(): Promise<void> {
        this.playlists.clearQuickList();
    }

    @bind @action public async handleSave(): Promise<void> {
        this.loading = true;
        await this.playlists.saveQuickList(this.description || this.descriptionPlaceholder);
        this.loading = false;
    }

    @bind @action public async handleRemoveItem(index: number): Promise<void> {
        if (this.loading) {
            return;
        }
        this.playlists.removeQuickListEntry(index);
    }

    @bind @action public handleDescription(event: React.SyntheticInputEvent): void {
        this.description = event.currentTarget.value;
    }

    @bind @action public handleDropdownClick(): void {
        this.open = !this.open;
    }

    public render(): JSX.Element {
        if (!this.visible) {
            return null;
        }
        return (
            <div className={css.container}>
                <Menu inverted color="violet" className={css.quickList}>
                    <Menu.Item>
                        <Input
                            onChange={this.handleDescription}
                            inverted
                            icon="file"
                            transparent
                            placeholder="Enter name..."
                        />
                    </Menu.Item>
                    <Dropdown item text={this.dropdownText} upward onClick={this.handleDropdownClick} open={this.open}>
                        <Dropdown.Menu
                            direction={this.open ? "left" : undefined}
                            disabled={this.loading}
                            open={this.open}
                        >
                            {this.playlists.quickList.map((entry, index) => {
                                return (
                                    <Dropdown.Item key={index} className={css.item} disabled={this.loading}>
                                        <Icon
                                            onClick={() => this.handleRemoveItem(index)}
                                            name="minus"
                                            className={classNames("right", "floated", css.icon)}
                                        />
                                        <Label circular content={index + 1} />
                                        <span className={css.dropdownContent}>{entry.sound.description}</span>
                                    </Dropdown.Item>
                                );
                            })}
                        </Dropdown.Menu>
                    </Dropdown>
                    <Menu.Item icon="play" color="blue" onClick={this.handlePlay} disabled={this.loading} />
                    <Menu.Item icon="remove" color="red" onClick={this.handleClear} disabled={this.loading} />
                    <Menu.Item icon="save" color="red" onClick={this.handleSave} disabled={this.loading} />
                </Menu>
            </div>
        );
    }
}
