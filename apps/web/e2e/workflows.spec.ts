import { expect, test } from "@playwright/test";
test("private dashboard and profile work without overflow", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "A little clarity. A lot of possibility.",
    }),
  ).toBeVisible();
  await expect(page.getByText("Running locally")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/" + info.project.name + "-dashboard.png",
    fullPage: true,
  });
  await page.goto("/profile");
  await expect(page.getByLabel("Name / display name")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add fact" }).first(),
  ).toBeVisible();
});
test("capture, fit, document review and explicit manual submission", async ({
  page,
}, info) => {
  await page.goto("/applications");
  await page.getByRole("button", { name: "Add a job manually" }).click();
  await page
    .getByLabel("Job title", { exact: true })
    .fill("Junior Civil Engineer " + info.project.name + " " + Date.now());
  await page
    .getByLabel("Employer", { exact: true })
    .fill("Example Infrastructure (fictional)");
  await page.getByLabel("City / region").fill("Regina");
  await page
    .getByLabel("Original job URL")
    .fill(
      "https://example.invalid/jobs/" + info.project.name + "/" + Date.now(),
    );
  await page
    .getByLabel("Full job description")
    .fill(
      "Full-time civil infrastructure. Required qualifications: Python and QGIS.",
    );
  await page.getByRole("button", { name: "Save job for review" }).click();
  await expect(
    page.getByRole("heading", { name: "Fit & eligibility review" }),
  ).toBeVisible();
  await expect(page.getByText("I have (confirmed):").first()).toBeVisible();
  await page.getByLabel("I checked this opening").check();
  await expect(page.getByText("verified", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Generate resume", exact: true })
    .click();
  await expect(
    page.getByText(
      "Source claims checked against your current verified profile.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "I reviewed and approve this draft" })
    .click();
  await page.getByLabel("Application stage").selectOption("Draft Ready");
  await page.getByRole("button", { name: "Save stage", exact: true }).click();
  await expect(
    page.getByText("Draft Ready", { exact: true }).first(),
  ).toBeVisible();
  await page.getByLabel("Application stage").selectOption("Approved");
  await page.getByLabel("I reviewed the original vacancy").check();
  await page.getByRole("button", { name: "Save stage", exact: true }).click();
  await expect(
    page.getByText("Approved", { exact: true }).first(),
  ).toBeVisible();
  await page.getByLabel("Application stage").selectOption("Submitted");
  await page
    .getByLabel("Evidence of the manual submission")
    .fill("Fictional test confirmation; no real submission made.");
  await page.getByRole("button", { name: "Save stage", exact: true }).click();
  await expect(
    page.getByText("Submission recorded", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("Review manual follow-up after 7 days"),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("preferences and honest source failure are usable", async ({ page }) => {
  await page.goto("/preferences");
  await expect(
    page.getByRole("heading", { name: "Country priorities" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save preferences", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Preferences saved");
  await page.goto("/search");
  await page
    .getByRole("button", { name: "Search opportunities", exact: true })
    .click();
  await expect(
    page.getByText("No enabled verified employer feeds.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByText("No matching vacancies returned.", { exact: false }),
  ).toBeVisible();
});
test("unauthenticated browser cannot read personal API data", async ({
  browser,
}) => {
  const ctx = await browser.newContext({
    storageState: { cookies: [], origins: [] },
  });
  const r = await ctx.request.get("http://127.0.0.1:3100/api/profile");
  expect(r.status()).toBe(401);
  await ctx.close();
});
