import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import path from "node:path";
const root = path.resolve(__dirname, "../..");
export default defineConfig({
  testDir: "e2e",
  testMatch: "**/*.spec.ts",
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  globalSetup: "./e2e/setup.ts",
  use: {
    baseURL: "http://127.0.0.1:3100",
    storageState: "test-results/session.json",
    launchOptions: existsSync("/usr/bin/chromium")
      ? { executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] }
      : {},
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `"${root}/apps/api/.venv/${process.platform === "win32" ? "Scripts/python.exe" : "bin/python"}" "${root}/apps/web/e2e/fixture_api.py"`,
      cwd: root + "/apps/api",
      url: "http://127.0.0.1:8100/health",
      timeout: 60000,
    },
    {
      command: "npm run start -- --port 3100",
      cwd: root + "/apps/web",
      url: "http://127.0.0.1:3100",
      timeout: 60000,
      env: {
        API_BASE_URL: "http://127.0.0.1:8100",
        API_TOKEN: "browser-fixture-only-token-000000000000000",
        SESSION_SECRET: "browser-fixture-only-session-00000000000000000000",
        APP_ORIGIN: "http://127.0.0.1:3100",
        CAREERPILOT_BOOTSTRAP_CODE: "browser-fixture-code-000000000000000",
        CAREERPILOT_BOOTSTRAP_DEADLINE: String(Date.now() + 300000),
      },
    },
  ],
});
