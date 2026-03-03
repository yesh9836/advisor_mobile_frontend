import { expect, test, type Page } from "@playwright/test";

const backendBaseUrl = (process.env.PLAYWRIGHT_E2E_BACKEND_URL ?? "").replace(/\/+$/, "");
const advisorEmail = process.env.PLAYWRIGHT_E2E_ADVISOR_EMAIL ?? "advisor.demo@example.com";
const advisorPassword = process.env.PLAYWRIGHT_E2E_ADVISOR_PASSWORD ?? "Password123!";
const canRunBackendIntegratedSuite = backendBaseUrl.length > 0;
const isCi = Boolean(process.env.CI);

const loginAsAdvisor = async (page: Page): Promise<void> => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(advisorEmail);
  await page.getByLabel("Password").fill(advisorPassword);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 20_000 });
};

test.describe("backend-integrated auth and checkout smoke @integration", () => {
  test.skip(
    !canRunBackendIntegratedSuite && !isCi,
    "Set PLAYWRIGHT_E2E_BACKEND_URL to run backend-integrated browser smoke tests.",
  );
  test.beforeAll(() => {
    if (!canRunBackendIntegratedSuite && isCi) {
      throw new Error(
        "Missing PLAYWRIGHT_E2E_BACKEND_URL in CI. Backend-integrated e2e must run in CI and cannot be skipped.",
      );
    }
  });

  test("refreshes session after replacing access cookie with an invalid value", async ({
    page,
    context,
  }) => {
    await loginAsAdvisor(page);

    const existingCookies = await context.cookies(backendBaseUrl);
    const refreshCookie = existingCookies.find((cookie) => cookie.name === "refresh_token");
    expect(refreshCookie).toBeTruthy();

    const backendOrigin = new URL(backendBaseUrl);
    await context.addCookies([
      {
        name: "access_token",
        value: "invalid-e2e-access-token",
        domain: backendOrigin.hostname,
        path: "/api/v1",
        httpOnly: true,
        secure: false,
        sameSite: "Lax",
        expires: Math.floor(Date.now() / 1000) + 60 * 30,
      },
    ]);

    await page.goto("/profile");
    await expect(page).toHaveURL(/\/profile$/, { timeout: 20_000 });
    await expect(
      page.getByRole("heading", { name: "Advisor Profile" }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page).not.toHaveURL(/\/login$/);
  });

  test("renders checkout return fulfillment summary from real purchase history", async ({
    page,
  }) => {
    await loginAsAdvisor(page);

    const historyResponse = await page.request.get(`${backendBaseUrl}/api/v1/purchases/history`, {
      params: { size: 20 },
    });
    expect(historyResponse.ok()).toBe(true);

    const historyPayload = (await historyResponse.json()) as {
      items?: Array<{ stripe_checkout_session_id?: string | null }>;
    };
    const checkoutSessionId = historyPayload.items?.find(
      (item) => typeof item?.stripe_checkout_session_id === "string" && item.stripe_checkout_session_id,
    )?.stripe_checkout_session_id;
    expect(checkoutSessionId).toBeTruthy();

    await page.goto(
      `/subscription?checkout=success&session_id=${encodeURIComponent(checkoutSessionId as string)}`,
    );
    await expect(page.getByText(/Checkout completed\. Delivered now:/)).toBeVisible({
      timeout: 20_000,
    });
  });
});
