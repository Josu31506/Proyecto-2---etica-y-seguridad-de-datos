import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const root = resolve(__dirname, "..");
const py =
  process.platform === "win32"
    ? ".venv\\Scripts\\python.exe"
    : ".venv/bin/python";
const state = mkdtempSync(join(tmpdir(), "alzace-e2e-"));
export default defineConfig({
  testDir: "./e2e",
  timeout: 45000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:13090",
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  },
  webServer: [
    {
      command:
        py +
        " -m backend.cli init && " +
        py +
        " -m uvicorn backend.main:app --host 127.0.0.1 --port 18090 --no-access-log",
      cwd: root,
      url: "http://127.0.0.1:18090/api/health",
      timeout: 90000,
      reuseExistingServer: false,
      env: {
        ALZACE_STATE: state,
        ALZACE_MODE: "demo",
        DATABASE_URL: "",
        FRONTEND_ORIGIN: "http://127.0.0.1:13090",
        DEMO_SHORTCUTS: "1",
      },
    },
    {
      command: "npm run build && npm run start -- --port 13090",
      url: "http://127.0.0.1:13090",
      timeout: 120000,
      reuseExistingServer: false,
      env: {
        ALZACE_FRONTEND_DIST: ".next-qa",
        API_INTERNAL_URL: "http://127.0.0.1:18090",
        NEXT_TELEMETRY_DISABLED: "1",
      },
    },
  ],
});
