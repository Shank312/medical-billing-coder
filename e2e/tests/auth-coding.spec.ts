import { expect, test } from "@playwright/test";
import { login, registerOrg } from "./helpers";

const NOTE = "Patient presents with major depressive disorder.";

test("login, create encounter, code, and review a suggestion", async ({ page, request }) => {
  const email = `e2e-coding-${Date.now()}@example.com`;
  await registerOrg(request, email);
  await login(page, email);

  // Create an encounter.
  await page.getByRole("link", { name: "New encounter" }).click();
  await page.getByLabel("Date of service").fill("2025-03-15");
  await page.getByLabel("Clinical note").fill(NOTE);
  await page.getByRole("button", { name: "Create encounter" }).click();
  await page.waitForURL(/\/encounters\/[0-9a-f-]+/);

  // Submit coding and wait for the async job to complete.
  await page.getByRole("button", { name: "Run coding" }).click();
  await expect(page.getByText("Coding completed.")).toBeVisible({ timeout: 30_000 });

  // The deterministic mock provider returns F32.9, which should be visible.
  await expect(page.getByText("F32.9")).toBeVisible();

  // Review (approve) the suggestion; the label reflects only a persisted decision.
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText("Approved").first()).toBeVisible();
});

test("cross-tenant access is rejected", async ({ page, request }) => {
  const suffix = Date.now();
  const orgA = await registerOrg(request, `a-${suffix}@example.com`);
  await login(page, `a-${suffix}@example.com`);

  // Create an encounter in org A, then capture its id from the URL.
  await page.getByRole("link", { name: "New encounter" }).click();
  await page.getByLabel("Date of service").fill("2025-03-15");
  await page.getByLabel("Clinical note").fill(NOTE);
  await page.getByRole("button", { name: "Create encounter" }).click();
  await page.waitForURL(/\/encounters\/[0-9a-f-]+/);
  const encounterId = page.url().split("/").pop()!;

  // A second organization cannot read org A's encounter via the API.
  const response = await request.get(`${process.env.E2E_API_URL ?? "http://localhost:8001"}/api/v1/encounters/${encounterId}`, {
    headers: { Authorization: `Bearer ${orgA.access_token}` },
  });
  expect(response.status()).toBe(200);

  const other = await registerOrg(request, `b-${suffix}@example.com`);
  const denied = await request.get(`${process.env.E2E_API_URL ?? "http://localhost:8001"}/api/v1/encounters/${encounterId}`, {
    headers: { Authorization: `Bearer ${other.access_token}` },
  });
  expect(denied.status()).toBe(404);
});
