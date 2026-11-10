// THE WALK'S BROWSER: Chromium at the audit's 1440 × 900, one desk served by `desk_walk.py`, and a
// baseline per page and platform in `desk_walk/`, since a Mac and GitHub's Linux set type apart.
import { defineConfig } from "@playwright/test";

const PORT = 8771;
// THE DAY THE DESK IS DRAWN ON, held in the server and in the page: the day of the audit.
export const DAY = "2026-11-10T12:00:00";

export default defineConfig({
  testDir: ".",
  testMatch: "desk_walk.spec.mjs",
  snapshotPathTemplate: "desk_walk/{arg}-{platform}{ext}",
  outputDir: "desk_walk_results",
  reporter: "list",
  workers: 1,
  forbidOnly: true,
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    browserName: "chromium",
    viewport: { width: 1440, height: 900 },
    colorScheme: "light",
    locale: "en-GB",
    timezoneId: "Europe/London",
  },
  webServer: {
    command: `python3 desk_walk.py ${PORT} ${DAY}`,
    url: `http://127.0.0.1:${PORT}/api/state`,
    reuseExistingServer: false,
  },
});
