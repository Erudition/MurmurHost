type MumbleAgent = import("../test-utils/mumble-agent").MumbleAgent;
type Page = import("puppeteer").Page;
type Browser = import("puppeteer").Browser;

declare const page: Page;
declare const browser: Browser;
declare const mumbleAgent: MumbleAgent;

declare namespace NodeJS {
    interface Global {
        page: Page;
        browser: Browser;
        mumbleAgent: MumbleAgent;
    }
}
