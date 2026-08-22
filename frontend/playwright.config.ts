import { defineConfig, devices } from "@playwright/test";

// The production build (frontend/dist) is served directly by the FastAPI
// backend on a single origin -- the same setup used in the real Docker
// deployment (see backend/app/main.py's static-serving block) -- rather than
// through Vite's dev server. Run `npm run build` before `npm run test:e2e`.
// The command also needs a Python environment with the backend dependencies;
// set PYTHON_BIN when the active `python3` is not that environment.
//
// KNOWN FLAKE (documented, not silently retried away): the second test
// ("URL updates with a shareable run id...") intermittently fails to see
// the reloaded page's UI update within the timeout, even against this
// production build. Investigated extensively: debug logging confirmed the
// app's own code runs correctly every single time in the failing case too
// (the fetch succeeds, the response contains correct data, and setResult()
// is called with it) -- the failure is that the browser never paints the
// resulting DOM change in time under Playwright's CDP automation. It has
// never reproduced under manual/real browser use. Root cause unresolved;
// retries mitigate it without hiding a real regression (an actual app bug
// would fail deterministically, not ~1 time in 4-8 runs).
export default defineConfig({
  testDir: "./e2e",
  // Must exceed the longest per-assertion wait used in the specs (currently
  // the 90_000ms wait for a real rolling-window optimization run) -- the
  // global test timeout fires before an inner locator timeout ever gets the
  // chance to, so a spec waiting longer than this always fails regardless
  // of app correctness.
  timeout: 120_000,
  fullyParallel: false,
  // The webServer below is a single uvicorn process with no worker pool, so
  // two Playwright workers running CPU-bound optimization requests at the
  // same time make the backend thrash: a solve that takes ~15-20s alone
  // measured 76-107s under concurrent load in CI (see optimize request
  // duration= log lines), blowing past even generous per-assertion
  // timeouts. Serializing workers removes the contention rather than
  // chasing a timeout that would still be flaky under load.
  workers: 1,
  retries: 2,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8001",
    trace: "retain-on-failure"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: {
    command: `${process.env.PYTHON_BIN ?? "python3"} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001`,
    url: "http://127.0.0.1:8001/api/health",
    reuseExistingServer: true,
    cwd: "..",
    timeout: 30_000
  }
});
