import { expect, test } from "@playwright/test";

// End-to-end happy path against the real running app and real cached SEC
// NAV data (see playwright.config.ts's webServer) -- no mocked network
// responses, so this exercises the actual calculation path, not just UI
// wiring.

test("select funds -> set assumptions -> run -> view optimization results", async ({ page }) => {
  await page.goto("/");

  // --- Step 1: Portfolio ---
  await expect(page.getByRole("heading", { name: "Build your portfolio" })).toBeVisible();
  await page.getByRole("button", { name: "Load an example portfolio" }).click();

  await page.getByRole("button", { name: "Continue to Assumptions" }).click();

  // --- Step 2: Assumptions ---
  await expect(page.getByRole("heading", { name: "Set the optimization objective" })).toBeVisible();
  // Defaults from the app's initial request are already a valid, runnable
  // configuration -- the happy path doesn't need to change anything here.
  await page.getByRole("button", { name: "Run optimization" }).click();

  // --- Step 3: Results ---
  // A real optimization against real SEC NAV data takes a moment; wait for the
  // actual result heading rather than a fixed sleep.
  await expect(page.getByText("Optimization result", { exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole("heading", { name: /Maximize Sharpe Ratio.*2 funds/ })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Performance", exact: true })).toBeVisible();

  // No error banner should be present on a successful run.
  await expect(page.locator(".banner")).toHaveCount(0);

  // The result must be computed from real cached SEC Open Data, not a mock --
  // the app's own client-side guard (assertSecOnly) would have thrown before
  // rendering anything if the API ever returned another data source, but
  // assert the Report tab's data-provenance text as a second, visible signal.
  await page.getByRole("tab", { name: "Report", exact: true }).click();
  await expect(page.getByText(/SEC Open Data/i)).toBeVisible();
});

test("URL updates with a shareable run id, and reloading it reproduces the result", async ({ page, browser }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load an example portfolio" }).click();
  await page.getByRole("button", { name: "Continue to Assumptions" }).click();
  await page.getByRole("button", { name: "Run optimization" }).click();
  await expect(page.getByText("Optimization result", { exact: true })).toBeVisible({ timeout: 60_000 });

  await expect(page).toHaveURL(/[?&]run=run_\d{8}_\d{6}_[0-9a-f]{32}/);
  const sharedUrl = page.url();
  const resultHeading = page.getByRole("heading", { name: /Maximize Sharpe Ratio.*2 funds/ });
  const resultHeadingText = await resultHeading.innerText();

  // Simulate a different visitor opening the shared link: a fresh browser
  // context/page, not a reload of the page that just ran the backtest --
  // this is what actually happens when a link is shared, and avoids any
  // leftover state (Vite HMR socket, SPA history) from the page that made
  // the original run.
  const visitorContext = await browser.newContext();
  const visitorPage = await visitorContext.newPage();
  try {
    await visitorPage.goto(sharedUrl);
    await expect(visitorPage.getByText("Optimization result", { exact: true })).toBeVisible({ timeout: 60_000 });
    const reloadedHeadingText = await visitorPage.getByRole("heading", { name: /Maximize Sharpe Ratio.*2 funds/ }).innerText();
    expect(reloadedHeadingText).toBe(resultHeadingText);
  } finally {
    await visitorContext.close();
  }
});
