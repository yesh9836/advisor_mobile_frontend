import { expect, test, type Page, type Route } from "@playwright/test";

const advisorUser = {
  id: 1,
  email: "advisor.e2e@example.com",
  name: "E2E Advisor",
  phone: "555-0000",
  role: "advisor",
  stripe_customer_id: null,
  created_at: "2026-02-20T00:00:00Z",
};

const packagePayload = [
  {
    id: 1,
    name: "Starter",
    price_cents: 20000,
    currency: "USD",
    stripe_price_id: "price_starter",
    state_limit: 1,
    daily_download_limit: 10,
    features: ["10 leads"],
    created_at: "2026-02-20T00:00:00Z",
  },
];

const verifiedLicensePayload = [
  {
    id: 10,
    user_id: 1,
    state: "CA",
    license_number: "CA-VERIFIED-100",
    license_type: "Series 65",
    has_document: true,
    verification_status: "verified",
    verified_at: "2026-02-20T00:00:00Z",
    verified_by: 2,
    rejection_reason: null,
    created_at: "2026-02-20T00:00:00Z",
  },
];

const defaultLeadsDashboardSummary = {
  leads_delivered_7_days: 3,
  appointments_set_7_days: 1,
  cost_per_appointment: 100.0,
  currency: "USD",
  settings: {
    email_alerts_enabled: true,
    sms_alerts_enabled: false,
    target_states: ["CA"],
    min_assets: null,
    daily_download_limit: 10,
  },
};

const defaultLeadsResponse = {
  items: [],
  total: 0,
  page: 1,
  size: 3,
};

const defaultDeliverySettings = {
  email_alerts_enabled: true,
  sms_alerts_enabled: false,
  version: 1,
  updated_at: "2026-02-20T00:00:00Z",
  warnings: [],
};

type ApiRouteHandler = (route: Route) => Promise<void>;
type ApiRouteMap = Record<string, ApiRouteHandler>;

const normalizePath = (pathname: string): string =>
  pathname.replace(/\/+$/, "") || "/";

const requestRouteKey = (route: Route): string => {
  const request = route.request();
  const url = new URL(request.url());
  return `${request.method().toUpperCase()} ${normalizePath(url.pathname)}`;
};

const fulfillJson = async (
  route: Route,
  body: unknown,
  status = 200,
): Promise<void> => {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
};

const setupApiMockRouter = async (
  page: Page,
  overrides: ApiRouteMap = {},
): Promise<{ assertNoUnhandledApiRequests: () => void }> => {
  const unhandledApiRequests: string[] = [];

  const defaultRoutes: ApiRouteMap = {
    "GET /api/v1/auth/me": async (route) => fulfillJson(route, advisorUser),
    "POST /api/v1/auth/refresh": async (route) => {
      await route.fulfill({
        status: 204,
        headers: {
          "set-cookie": "csrf_token=csrf-refresh-token; Path=/; SameSite=Lax",
        },
      });
    },
    "GET /api/v1/licenses": async (route) =>
      fulfillJson(route, verifiedLicensePayload),
    "GET /api/v1/purchases/packages": async (route) =>
      fulfillJson(route, packagePayload),
    "GET /api/v1/purchases/history": async (route) =>
      fulfillJson(route, { items: [] }),
    "GET /api/v1/purchases/billing/summary": async (route) =>
      fulfillJson(route, {
        payment_method: null,
        invoices: [],
        provider_status: "healthy",
        degradation_reason: null,
      }),
    "GET /api/v1/purchases/first-purchase-offer": async (route) =>
      fulfillJson(route, { eligible: false, offer: null }),
    "GET /api/v1/purchases/balance": async (route) =>
      fulfillJson(route, {
        total_credits: 10,
        remaining_credits: 10,
        completed_purchases: 1,
      }),
    "GET /api/v1/leads/dashboard/summary": async (route) =>
      fulfillJson(route, defaultLeadsDashboardSummary),
    "GET /api/v1/leads": async (route) =>
      fulfillJson(route, defaultLeadsResponse),
    "GET /api/v1/delivery-settings/me": async (route) =>
      fulfillJson(route, defaultDeliverySettings),
  };

  const routes: ApiRouteMap = {
    ...defaultRoutes,
    ...overrides,
  };

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const key = requestRouteKey(route);
    const handler = routes[key];

    if (!handler) {
      unhandledApiRequests.push(`${request.method()} ${url.pathname}${url.search}`);
      await fulfillJson(
        route,
        { detail: `Unhandled e2e API mock for ${request.method()} ${url.pathname}` },
        501,
      );
      return;
    }

    await handler(route);
  });

  return {
    assertNoUnhandledApiRequests: () => {
      expect(
        unhandledApiRequests,
        `Unexpected unmocked API requests:\n${unhandledApiRequests.join("\n")}`,
      ).toEqual([]);
    },
  };
};

test.describe("critical auth and checkout browser journeys @mocked", () => {
  test("uses auth cookies and CSRF header when starting checkout", async ({
    page,
    baseURL,
  }) => {
    let isAuthenticated = false;
    let capturedCsrfHeader: string | null = null;

    const { assertNoUnhandledApiRequests } = await setupApiMockRouter(page, {
      "GET /api/v1/auth/me": async (route) => {
        if (!isAuthenticated) {
          await fulfillJson(route, { detail: "Unauthenticated" }, 401);
          return;
        }
        await fulfillJson(route, advisorUser);
      },
      "POST /api/v1/auth/login": async (route) => {
        isAuthenticated = true;
        await route.fulfill({
          status: 204,
          headers: {
            "set-cookie": "csrf_token=csrf-e2e-token; Path=/; SameSite=Lax",
          },
        });
      },
      "POST /api/v1/purchases/checkout": async (route) => {
        capturedCsrfHeader = await route.request().headerValue("x-csrf-token");
        await fulfillJson(route, {
          session_id: "cs_e2e_checkout",
          url: `${baseURL}/subscription?checkout=success&session_id=cs_e2e_checkout`,
        });
      },
    });

    await page.goto("/login");
    await page.getByLabel("Email").fill(advisorUser.email);
    await page.getByLabel("Password").fill("StrongPass123!");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("link", { name: "Buy Leads" }).click();
    await expect(page).toHaveURL(/\/subscription$/);
    await page.getByRole("button", { name: "Checkout" }).click();

    await expect(page).toHaveURL(/checkout=success/);
    expect(capturedCsrfHeader).toBe("csrf-e2e-token");
    assertNoUnhandledApiRequests();
  });

  test("refreshes cookie session and retries failed request on transient 401", async ({
    page,
  }) => {
    let balanceCalls = 0;
    let refreshCalls = 0;

    const { assertNoUnhandledApiRequests } = await setupApiMockRouter(page, {
      "POST /api/v1/auth/refresh": async (route) => {
        refreshCalls += 1;
        await route.fulfill({
          status: 204,
          headers: {
            "set-cookie": "csrf_token=csrf-refresh-token; Path=/; SameSite=Lax",
          },
        });
      },
      "GET /api/v1/licenses": async (route) => fulfillJson(route, []),
      "GET /api/v1/purchases/history": async (route) =>
        fulfillJson(route, { items: [] }),
      "GET /api/v1/purchases/balance": async (route) => {
        balanceCalls += 1;

        if (balanceCalls === 1) {
          await fulfillJson(route, { detail: "expired access token" }, 401);
          return;
        }

        await fulfillJson(route, {
          total_credits: 10,
          remaining_credits: 6,
          completed_purchases: 1,
        });
      },
    });

    await page.goto("/profile");

    await expect(page).toHaveURL(/\/profile$/, { timeout: 20_000 });
    await expect(
      page.getByRole("heading", { name: "Advisor Profile" }),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page).not.toHaveURL(/\/login$/);
    expect(refreshCalls).toBe(1);
    expect(balanceCalls).toBeGreaterThanOrEqual(2);
    assertNoUnhandledApiRequests();
  });

  test("forces logout redirect when refresh fails with terminal 401", async ({
    page,
  }) => {
    let refreshCalls = 0;
    let balanceCalls = 0;
    let sessionActive = true;

    const { assertNoUnhandledApiRequests } = await setupApiMockRouter(page, {
      "GET /api/v1/auth/me": async (route) => {
        if (!sessionActive) {
          await fulfillJson(route, { detail: "Unauthenticated" }, 401);
          return;
        }
        await fulfillJson(route, advisorUser);
      },
      "POST /api/v1/auth/refresh": async (route) => {
        refreshCalls += 1;
        sessionActive = false;
        await fulfillJson(route, { detail: "Refresh session expired" }, 401);
      },
      "GET /api/v1/licenses": async (route) => fulfillJson(route, []),
      "GET /api/v1/purchases/history": async (route) =>
        fulfillJson(route, { items: [] }),
      "GET /api/v1/purchases/balance": async (route) => {
        balanceCalls += 1;
        await fulfillJson(route, { detail: "expired access token" }, 401);
      },
    });

    await page.goto("/profile");

    await expect(page).toHaveURL(/\/login$/, { timeout: 20_000 });
    await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible({
      timeout: 20_000,
    });
    expect(refreshCalls).toBeGreaterThanOrEqual(1);
    expect(balanceCalls).toBeGreaterThanOrEqual(1);
    assertNoUnhandledApiRequests();
  });

  test("renders checkout return fulfillment summary after Stripe redirect", async ({
    page,
  }) => {
    const { assertNoUnhandledApiRequests } = await setupApiMockRouter(page, {
      "GET /api/v1/purchases/history": async (route) => {
        await fulfillJson(route, {
          items: [
            {
              id: 1,
              order_reference: "ORD-1",
              package_name: "Starter",
              amount_cents: 20000,
              currency: "USD",
              credits_total: 10,
              entitled_credits_total: 10,
              credits_remaining: 4,
              status: "completed",
              assigned_count: 6,
              unfulfilled_count: 4,
              fulfillment_status: "partially_fulfilled",
              purchased_at: "2026-02-20T00:00:00Z",
              stripe_checkout_session_id: "cs_return_1",
              stripe_payment_intent_id: "pi_return_1",
            },
          ],
        });
      },
    });

    await page.goto("/");
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.getByRole("link", { name: "Buy Leads" }).click();
    await expect(page).toHaveURL(/\/subscription$/);
    await page.evaluate(() => {
      window.history.replaceState(
        {},
        "",
        "/subscription?checkout=success&session_id=cs_return_1",
      );
      window.dispatchEvent(new PopStateEvent("popstate"));
    });

    await expect(
      page.getByText("Checkout completed. Delivered now: 6/10. Pending auto-delivery: 4."),
    ).toBeVisible({ timeout: 20_000 });
    assertNoUnhandledApiRequests();
  });

  test("renders billing fallback notice when provider is degraded", async ({ page }) => {
    const { assertNoUnhandledApiRequests } = await setupApiMockRouter(page, {
      "GET /api/v1/purchases/billing/summary": async (route) => {
        await fulfillJson(route, {
          payment_method: null,
          invoices: [
            {
              stripe_invoice_id: "in_degraded_1",
              amount_paid_cents: 18000,
              currency: "USD",
              status: "paid",
              created_at: "2026-02-28T00:00:00Z",
              package_name: "Starter",
              hosted_invoice_url: null,
              invoice_pdf: null,
              description: null,
            },
          ],
          provider_status: "degraded",
          degradation_reason: "stripe_unavailable",
        });
      },
    });

    await page.goto("/billing");

    await expect(
      page.getByText("Stripe billing details are temporarily unavailable. Showing purchase history."),
    ).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Starter")).toBeVisible({ timeout: 20_000 });
    assertNoUnhandledApiRequests();
  });
});
