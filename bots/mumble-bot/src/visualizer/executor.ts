import { info, verbose } from "winston";
import { spawn } from "child_process";
import { component, initialize, inject } from "tsdi";
import { ServerConfig } from "../config/server-config";

@component
export class VisualizerExecutor {
    @inject private readonly config!: ServerConfig;

    private get baseCommand(): string[] {
        const relevantArgs = [];
        for (let i = 0; i < process.argv.length; ++i) {
            const arg = process.argv[i];
            if (arg === "serve") {
                relevantArgs.push("visualize");
                return relevantArgs;
            }
            relevantArgs.push(arg);
        }
    }

    private run(...args: string[]): Promise<void> {
        return new Promise((resolve, reject) => {
            const [executable, ...path] = this.baseCommand;
            verbose(`Starting visualizer: ${[executable, ...path, ...args].join(" ")}`);
            const config = ["--sounds-dir", this.config.soundsDir, "--tmp-dir", this.config.tmpDir];
            const child = spawn(executable, [...path, ...args, ...config]);
            child.on("exit", (code) => {
                if (code === 0) {
                    resolve();
                    return;
                }
                reject();
            });
            child.stdout.on("data", (line) => {
                info(`From visualizer: ${line.toString().trim()}`);
            });
        });
    }

    public visualizeSound(id: string): Promise<void> {
        return this.run("--sound-id", id);
    }

    public visualizeCached(id: string): Promise<void> {
        return this.run("--cached-id", id);
    }

    @initialize
    public recheck(): Promise<void> {
        return this.run("--recheck", "true");
    }
}
