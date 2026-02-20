import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:5173",
    headless: true,
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  webServer: [
    {
      command: "cd .. && .venv/bin/uvicorn cannalchemy.api.app:app --port 8421",
      port: 8421,
      timeout: 120000,
      reuseExistingServer: true,
    },
    {
      command: "npx vite --port 5173",
      port: 5173,
      timeout: 15000,
      reuseExistingServer: true,
    },
  ],
});
