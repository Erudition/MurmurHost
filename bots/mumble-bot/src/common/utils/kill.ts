import { error, warn } from "winston";

export function onKill(callback: () => void): void {
    let killed = false;
    const kill = async (): Promise<void> => {
        if (killed) {
            error("CTRL^C detected. Terminating!");
            // eslint-disable-next-line no-process-exit
            process.exit(1);
        }
        killed = true;
        warn("CTRL^C detected. Secure shutdown initiated.");
        warn("Press CTRL^C again to terminate at your own risk.");
        callback();
    };
    process.on("SIGINT", kill);
}
