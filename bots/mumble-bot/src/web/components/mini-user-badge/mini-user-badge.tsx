import * as React from "react";
import { Link } from "react-router-dom";
import { Image } from "semantic-ui-react";
import { User } from "../../../common/models/user";
import { routeUser } from "../../routing/routing";
import * as css from "./mini-user-badge.scss";

export function MiniUserBadge({ user }: { user: User }): JSX.Element {
    return (
        <Link to={routeUser.path(user.id)}>
            <Image className={css.avatar} size="mini" avatar src={user.avatarUrl} />
            {user.name}
        </Link>
    );
}
