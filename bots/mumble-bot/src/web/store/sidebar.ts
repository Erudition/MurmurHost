import { observable, computed, action } from "mobx";
import { bind } from "decko";
import { component, initialize } from "tsdi";

import { breakpointL } from "../breakpoints";

@component
export class SidebarStore {
    @observable public visibilityToggled = false;
    @observable public alwaysOpen = this.calculateAlwaysOpen();

    private calculateAlwaysOpen(): boolean {
        return window.innerWidth >= breakpointL;
    }

    @bind
    private onWindowResize(): void {
        this.alwaysOpen = this.calculateAlwaysOpen();
    }

    @initialize public init(): void {
        window.addEventListener("resize", this.onWindowResize);
    }

    @computed public get visible(): boolean {
        return this.visibilityToggled || this.alwaysOpen;
    }

    @bind @action public toggleVisibility(): void {
        this.visibilityToggled = !this.visibilityToggled;
    }
}
