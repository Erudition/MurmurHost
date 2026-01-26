import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component } from "tsdi";

interface ApiError {
    message: string;
    fatal?: boolean;
}

@component
export class ErrorStore {
    @observable public errors: ApiError[] = [];

    @bind
    @action
    public report(error: ApiError): void {
        if (this.errors.find((other) => other.message === error.message)) {
            return;
        }
        this.errors.push(error);
    }

    @bind
    @action
    public dismiss(): void {
        this.errors.pop();
    }

    @computed
    public get latestError(): ApiError {
        return this.errors[this.errors.length - 1];
    }
}
