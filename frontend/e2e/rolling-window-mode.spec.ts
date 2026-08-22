import { expect, test } from "@playwright/test";

// End-to-end coverage for the rollingWindowMode control, against the real
// running app and real cached SEC NAV data (see playwright.config.ts's
// webServer) -- no mocked network responses.
//
// The specific regression this guards: the control is new, and the failure
// mode it could have is silent -- the UI shows "trailing" while the request
// that actually reaches POST /api/optimize still carries the "expanding"
// default (or omits the field entirely, which the backend also reads as
// expanding). Asserting the rendered Rolling tab alone wouldn't catch that,
// since both modes produce folds, so this asserts BOTH halves: the outgoing
// request body literally says "trailing", and the response it produced
// renders real fold rows rather than an empty table.

test("rollingWindowMode=trailing round-trips to the optimizer and returns fold data", async ({ page }) => {
  // Rolling evaluation solves one optimization per fold against the real SEC
  // cache, so it is intentionally slower than the basic happy path.
  test.setTimeout(120_000);
  await page.goto("/");

  // --- Step 1: Portfolio ---
  await expect(page.getByRole("heading", { name: "Build your portfolio" })).toBeVisible();
  await page.getByRole("button", { name: "Load an example portfolio" }).click();
  await page.getByRole("button", { name: "Continue to Assumptions" }).click();

  // --- Step 2: Assumptions ---
  await expect(page.getByRole("heading", { name: "Set the optimization objective" })).toBeVisible();

  // rollingWindowMode lives inside the collapsed "Rolling-window validation
  // & comparison" disclosure, which is closed by default.
  await page.getByText("Rolling-window validation & comparison").click();
  const modeSelect = page.locator("#rollingWindowMode");
  await expect(modeSelect).toBeVisible();
  await modeSelect.selectOption("trailing");
  await expect(modeSelect).toHaveValue("trailing");

  // Capture the actual request body rather than trusting the control's
  // displayed value -- this is the half that proves nothing silently
  // reverted to the "expanding" default on the way out.
  const optimizeRequest = page.waitForRequest((request) =>
    request.url().includes("/api/optimize") && request.method() === "POST"
  );

  await page.getByRole("button", { name: "Run optimization" }).click();

  const sentBody = (await optimizeRequest).postDataJSON();
  expect(sentBody.constraints.rollingWindowMode).toBe("trailing");

  // --- Step 3: Results ---
  // A real optimization over real SEC NAV data takes a moment; wait for the
  // result itself rather than a fixed sleep.
  await expect(page.getByText("Optimization result", { exact: true })).toBeVisible({ timeout: 90_000 });
  await expect(page.locator('[role="dialog"][aria-labelledby="run-overlay-title"]')).toBeHidden({ timeout: 30_000 });
  await expect(page.locator(".banner")).toHaveCount(0);

  await page.getByRole("tab", { name: "Rolling", exact: true }).click();
  const foldsPanel = page.locator(".tablePanel", { hasText: "Rolling out-of-sample folds" });
  await expect(foldsPanel).toBeVisible();
  // Non-empty fold data: the trailing-window schedule actually produced
  // folds, rather than the tab rendering an empty table.
  expect(await foldsPanel.locator("tbody tr").count()).toBeGreaterThan(0);
});
