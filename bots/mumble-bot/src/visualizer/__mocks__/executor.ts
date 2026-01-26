import { component } from "tsdi";

@component
export class VisualizerExecutor {
    public visualizeSound(_id: string): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, 10));
    }

    public visualizeCached(_id: string): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, 10));
    }

    public recheck(): Promise<void> {
        return new Promise((resolve) => setTimeout(resolve, 10));
    }
}
