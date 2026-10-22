import { expect, test } from "@playwright/test";
import { login, registerOrg } from "./helpers";

const NOTE = "Patient presents with major depressive disorder.";

test("export CSV, XLSX, and PDF summary", async ({ page, request }) => {
  const email = `e2e-export-${Date.now()}@example.com`;
  await registerOrg(request, email);
  await login(page, email);

  // Create + code one encounter so exports have content.
  await page.getByRole("link", { name: "New encounter" }).click();
  await page.getByLabel("Date of service").fill("2025-03-15");
  await page.getByLabel("Clinical note").fill(NOTE);
  await page.getByRole("button", { name: "Create encounter" }).click();
  await page.waitForURL(/\/encounters\/[0-9a-f-]+/);
  await page.getByRole("button", { name: "Run coding" }).click();
  await expect(page.getByText("Coding completed.")).toBeVisible({ timeout: 30_000 });

  // Per-encounter PDF summary.
  const pdf = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF summary" }).click();
  expect((await pdf).suggestedFilename()).toContain(".pdf");

  // Collection CSV + XLSX from the encounters dashboard.
  await page.getByRole("link", { name: "Encounters" }).first().click();
  await page.waitForURL("**/encounters");
  const csv = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await csv).suggestedFilename()).toContain(".csv");

  const xlsx = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export XLSX" }).click();
  expect((await xlsx).suggestedFilename()).toContain(".xlsx");
});
