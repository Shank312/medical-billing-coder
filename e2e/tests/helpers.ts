import type { APIRequestContext, Page } from "@playwright/test";

export const API_URL = process.env.E2E_API_URL ?? "http://localhost:8001";
export const PASSWORD = "correct-horse-battery-staple-123!";

export async function registerOrg(request: APIRequestContext, email: string) {
  const response = await request.post(`${API_URL}/api/v1/auth/register`, {
    data: {
      organization_name: `Org ${email}`,
      full_name: "Test Person",
      email,
      password: PASSWORD,
    },
  });
  if (!response.ok()) {
    throw new Error(`register failed: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL("**/encounters");
}
