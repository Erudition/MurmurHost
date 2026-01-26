import { component } from "tsdi";
import { createBrowserHistory, History } from "history";

@component
export class BrowserHistory {
    public readonly history = createBrowserHistory();

    public get push(): History["push"] {
        return this.history.push.bind(this.history);
    }

    public get replace(): History["replace"] {
        return this.history.replace.bind(this.history);
    }
}
