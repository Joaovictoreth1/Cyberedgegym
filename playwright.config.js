import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './frontend/tests',
    retries: 0,
    workers: 1,
    use: {
        baseURL: 'http://127.0.0.1:5501',
        launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE },
    },
    webServer: {
        command: 'python3 -m http.server --bind 127.0.0.1 --directory dist 5501',
        url: 'http://127.0.0.1:5501',
    },
});
