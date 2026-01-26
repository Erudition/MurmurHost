import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, inject, initialize } from "tsdi";
import { routeDashboard } from "../routing/routing";
import { Tokens } from "../../common/controllers/tokens";
import { Token } from "../../common/models/token";
import { User } from "../../common/models/user";
import { Subject } from "rxjs";
import { BrowserHistory } from "../factories/history";

const softwareVersion = 2;
const localStorageIdentifier = "software-login";

interface LocalStorageApi {
    readonly storageVersion: number;
    readonly date: string;
    readonly authToken: string;
    readonly userId: string;
}

@component
export class LoginStore {
    @inject private readonly tokens!: Tokens;
    @inject private readonly browserHistory!: BrowserHistory;

    @observable public authToken: string;
    @observable public userId: string;

    public onLogin$ = new Subject<void>();

    @initialize
    protected init(): void {
        this.load();
    }

    @computed
    public get loggedIn(): boolean {
        return typeof this.authToken !== "undefined" && typeof this.userId !== "undefined";
    }

    @bind
    @action
    public async login(email: string, password: string): Promise<Token> {
        const response = await this.tokens.createToken({ email, password } as User);
        if (response) {
            const { id, user } = response;
            this.authToken = id;
            this.userId = user.id;
            this.save();
            this.onLogin$.complete();
            this.browserHistory.replace(routeDashboard.path());
        }
        return response;
    }

    @bind
    @action
    public logout(): void {
        this.clearStorage();
        this.authToken = undefined;
        this.userId = undefined;
    }

    @bind
    private save(): void {
        const deserialized: LocalStorageApi = {
            storageVersion: softwareVersion,
            date: new Date().toString(),
            authToken: this.authToken,
            userId: this.userId,
        };
        const serialized = JSON.stringify(deserialized);
        localStorage.setItem(localStorageIdentifier, serialized);
    }

    @bind
    private clearStorage(): void {
        localStorage.removeItem(localStorageIdentifier);
    }

    @bind
    private load(): void {
        const serialized = localStorage.getItem(localStorageIdentifier);
        if (serialized === null) {
            return;
        }
        let deserialized: LocalStorageApi;
        try {
            deserialized = JSON.parse(serialized);
        } catch (err) {
            this.clearStorage();
            return;
        }
        if (deserialized.storageVersion !== softwareVersion) {
            this.clearStorage();
            return;
        }
        this.authToken = deserialized.authToken;
        this.userId = deserialized.userId;
        this.onLogin$.complete();
    }
}
