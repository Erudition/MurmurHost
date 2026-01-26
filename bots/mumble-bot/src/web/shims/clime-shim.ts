/* eslint-disable @typescript-eslint/no-explicit-any */
export class Options {}

export function option(..._args: any[]): (target: any, key: string) => void {
    return function (_target: any, _key: string): void {
        return;
    };
}
