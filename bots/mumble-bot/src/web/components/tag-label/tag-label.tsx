import * as React from "react";
import { bind } from "decko";
import { Label, Icon } from "semantic-ui-react";
import { Tag } from "../../../common/models/tag";

export interface TagLabelProps {
    tag: Tag;
    onClick?: () => void;
    onRemove?: () => void;
}

export class TagLabel extends React.Component<TagLabelProps> {
    @bind private handleClick(): void {
        if (this.props.onClick) {
            this.props.onClick();
        }
    }

    @bind private handleRemove(event: React.MouseEvent<HTMLDivElement>): void {
        event.stopPropagation();
        if (this.props.onRemove) {
            this.props.onRemove();
        }
    }

    public render(): JSX.Element {
        const { tag, onRemove } = this.props;
        return (
            <Label onClick={this.handleClick}>
                {tag.name}
                {onRemove && <Icon name="delete" onClick={this.handleRemove} />}
            </Label>
        );
    }
}
