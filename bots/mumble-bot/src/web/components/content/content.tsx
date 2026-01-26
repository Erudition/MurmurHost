import * as React from "react";

import * as css from "./content.scss";

export class Content extends React.Component {
    public render(): JSX.Element {
        return <div className={css.content}>{this.props.children}</div>;
    }
}
