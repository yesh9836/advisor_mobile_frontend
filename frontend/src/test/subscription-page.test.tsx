import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SubscriptionPage from "@/pages/advisor/SubscriptionPage";

vi.mock("@/api/purchases", () => ({
  getPackages: vi.fn().mockResolvedValue([]),
  createCheckout: vi.fn(),
  getFirstPurchaseOfferEligibility: vi.fn().mockResolvedValue({
    eligible: false,
    offer: null,
  }),
  getPurchaseHistory: vi.fn().mockResolvedValue({
    items: [],
  }),
}));

vi.mock("@/api/licenses", () => ({
  getMyLicenses: vi.fn().mockResolvedValue([]),
}));

const renderRoute = (route: string) => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route path="/subscription" element={<SubscriptionPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("SubscriptionPage checkout return messaging", () => {
  it("shows success notice when redirected from Stripe success URL", async () => {
    renderRoute("/subscription?checkout=success&session_id=cs_test_123");

    expect(
      await screen.findByText(/Checkout completed\. Your lead credits are available/),
    ).toBeInTheDocument();
    expect(await screen.findByText("No Packages Available")).toBeInTheDocument();
  });

  it("shows fulfillment details when matching checkout purchase is found", async () => {
    const { getPurchaseHistory } = await import("@/api/purchases");
    vi.mocked(getPurchaseHistory).mockResolvedValueOnce({
      items: [
        {
          id: 1,
          order_reference: "cs_test_123",
          package_name: "Starter",
          amount_cents: 20000,
          currency: "USD",
          credits_total: 10,
          entitled_credits_total: 10,
          credits_remaining: 10,
          status: "completed",
          assigned_count: 6,
          unfulfilled_count: 4,
          fulfillment_status: "partially_fulfilled",
          purchased_at: "2026-02-18T12:00:00Z",
          stripe_checkout_session_id: "cs_test_123",
          stripe_payment_intent_id: "pi_test_123",
        },
      ],
    });

    renderRoute("/subscription?checkout=success&session_id=cs_test_123");

    expect(
      await screen.findByText(
        "Checkout completed. Delivered now: 6/10. Pending auto-delivery: 4.",
      ),
    ).toBeInTheDocument();
  });

  it("shows cancel notice when redirected from Stripe cancel URL", async () => {
    renderRoute("/subscription?checkout=cancel");

    expect(
      screen.getByText("Checkout canceled. No charge was made."),
    ).toBeInTheDocument();
    expect(await screen.findByText("No Packages Available")).toBeInTheDocument();
  });
});

describe("SubscriptionPage license gate", () => {
  it("does not render internal object feature metadata on package cards", async () => {
    const { getPackages } = await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getPackages).mockResolvedValueOnce([
      {
        id: 11,
        name: "Growth 30",
        price_cents: 30000,
        currency: "USD",
        stripe_price_id: "price_growth_30",
        state_limit: 3,
        daily_download_limit: 30,
        features: {
          support: "email",
          credits_total: 30,
          catalog_visible: true,
        },
        created_at: "2026-02-26T00:00:00Z",
      },
    ]);
    vi.mocked(getMyLicenses).mockResolvedValueOnce([
      {
        id: 101,
        user_id: 1,
        state: "CA",
        license_number: "CA-VERIFIED-101",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);

    renderRoute("/subscription");

    expect(await screen.findByText("Growth 30")).toBeInTheDocument();
    expect(screen.queryByText(/support:\s*email/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/credits_total:\s*30/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/catalog_visible:\s*true/i)).not.toBeInTheDocument();
  });

  it("shows explicit no-license message and blocks checkout", async () => {
    const { getPackages } = await import("@/api/purchases");
    vi.mocked(getPackages).mockResolvedValueOnce([
      {
        id: 1,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        stripe_price_id: "price_starter",
        state_limit: 1,
        daily_download_limit: 10,
        features: ["10 leads"],
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);

    renderRoute("/subscription");

    expect(
      await screen.findByText("Submit a license from your profile to unlock lead checkout."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Profile" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "License Verification Required" }),
    ).toBeDisabled();
  });

  it("blocks checkout while license is pending review", async () => {
    const { getPackages } = await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getPackages).mockResolvedValueOnce([
      {
        id: 1,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        stripe_price_id: "price_starter",
        state_limit: 1,
        daily_download_limit: 10,
        features: ["10 leads"],
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getMyLicenses).mockResolvedValueOnce([
      {
        id: 99,
        user_id: 1,
        state: "CA",
        license_number: "CA-PENDING-001",
        license_type: "Series 65",
        has_document: true,
        verification_status: "pending",
        verified_at: null,
        verified_by: null,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);

    renderRoute("/subscription");

    expect(
      await screen.findByText(
        "Your license is pending admin review. Checkout unlocks after approval.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "License Verification Required" }),
    ).toBeDisabled();
  });

  it("enables checkout when advisor has a verified license", async () => {
    const { getPackages } = await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getPackages).mockResolvedValueOnce([
      {
        id: 1,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        stripe_price_id: "price_starter",
        state_limit: 1,
        daily_download_limit: 10,
        features: ["10 leads"],
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getMyLicenses).mockResolvedValueOnce([
      {
        id: 100,
        user_id: 1,
        state: "CA",
        license_number: "CA-VERIFIED-001",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);

    renderRoute("/subscription");

    expect(await screen.findByRole("button", { name: "Checkout" })).toBeEnabled();
    expect(
      screen.queryByText("Submit a license from your profile to unlock lead checkout."),
    ).not.toBeInTheDocument();
  });

  it("shows first-purchase add-on popup after first successful checkout and allows add-on checkout", async () => {
    const { getPurchaseHistory, getFirstPurchaseOfferEligibility, createCheckout } =
      await import("@/api/purchases");
    vi.mocked(getPurchaseHistory).mockResolvedValueOnce({
      items: [
        {
          id: 1,
          order_reference: "cs_test_123",
          package_name: "Starter",
          amount_cents: 20000,
          currency: "USD",
          credits_total: 10,
          entitled_credits_total: 10,
          credits_remaining: 10,
          status: "completed",
          assigned_count: 10,
          unfulfilled_count: 0,
          fulfillment_status: "fulfilled",
          purchased_at: "2026-02-19T00:00:00Z",
          stripe_checkout_session_id: "cs_test_123",
          stripe_payment_intent_id: "pi_test_123",
        },
      ],
    });
    vi.mocked(getFirstPurchaseOfferEligibility).mockResolvedValueOnce({
      eligible: true,
      offer: {
        trigger_package_id: 1,
        offer_package_id: 2,
        offer_package_name: "Starter Plus",
        offer_price_cents: 25000,
        offer_currency: "USD",
        offer_credits_total: 14,
        headline: "First order bonus",
        message: "Upgrade now for extra credits.",
        cta_label: "Upgrade package",
      },
    });
    vi.mocked(createCheckout).mockRejectedValueOnce(new Error("checkout unavailable"));

    renderRoute("/subscription?checkout=success&session_id=cs_test_123");

    expect(
      await screen.findByRole("heading", { name: "First order bonus" }),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Upgrade package" }));

    await waitFor(() => {
      expect(getFirstPurchaseOfferEligibility).toHaveBeenCalledWith("cs_test_123");
      expect(createCheckout).toHaveBeenCalledWith(2, expect.any(String));
    });
    expect(await screen.findByText("checkout unavailable")).toBeInTheDocument();
  });

  it("waits for purchase completion before checking first-purchase add-on eligibility", async () => {
    const { getPurchaseHistory, getFirstPurchaseOfferEligibility } =
      await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getMyLicenses).mockResolvedValueOnce([
      {
        id: 103,
        user_id: 1,
        state: "GA",
        license_number: "GA-VERIFIED-001",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getPurchaseHistory)
      .mockResolvedValueOnce({
        items: [
          {
            id: 1,
            order_reference: "cs_test_pending",
            package_name: "Starter",
            amount_cents: 20000,
            currency: "USD",
            credits_total: 10,
            entitled_credits_total: 10,
            credits_remaining: 10,
            status: "pending",
            assigned_count: 0,
            unfulfilled_count: 10,
            fulfillment_status: "pending",
            purchased_at: "2026-02-19T00:00:00Z",
            stripe_checkout_session_id: "cs_test_pending",
            stripe_payment_intent_id: "pi_test_pending",
          },
        ],
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 1,
            order_reference: "cs_test_pending",
            package_name: "Starter",
            amount_cents: 20000,
            currency: "USD",
            credits_total: 10,
            entitled_credits_total: 10,
            credits_remaining: 10,
            status: "completed",
            assigned_count: 10,
            unfulfilled_count: 0,
            fulfillment_status: "fulfilled",
            purchased_at: "2026-02-19T00:00:00Z",
            stripe_checkout_session_id: "cs_test_pending",
            stripe_payment_intent_id: "pi_test_pending",
          },
        ],
      })
      .mockResolvedValue({
        items: [],
      });
    vi.mocked(getFirstPurchaseOfferEligibility).mockResolvedValueOnce({
      eligible: true,
      offer: {
        trigger_package_id: 1,
        offer_package_id: 2,
        offer_package_name: "Starter Plus",
        offer_price_cents: 25000,
        offer_currency: "USD",
        offer_credits_total: 14,
        headline: "First order bonus",
        message: "Upgrade now for extra credits.",
        cta_label: "Upgrade package",
      },
    });

    renderRoute("/subscription?checkout=success&session_id=cs_test_pending");

    await screen.findByText(
      "Checkout completed. Delivered now: 0/10. Pending auto-delivery: 10.",
    );
    const callCountBeforeRetry = vi.mocked(getFirstPurchaseOfferEligibility).mock.calls.length;

    await waitFor(
      () => {
        expect(vi.mocked(getFirstPurchaseOfferEligibility).mock.calls.length).toBeGreaterThan(
          callCountBeforeRetry,
        );
        expect(getFirstPurchaseOfferEligibility).toHaveBeenCalledWith("cs_test_pending");
      },
      { timeout: 5000 },
    );
    expect(
      await screen.findByRole("heading", { name: "First order bonus" }),
    ).toBeInTheDocument();
  });

  it("maps structured inventory rejection codes for add-on checkout", async () => {
    const { getPurchaseHistory, getFirstPurchaseOfferEligibility, createCheckout } =
      await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getMyLicenses).mockResolvedValueOnce([
      {
        id: 104,
        user_id: 1,
        state: "GA",
        license_number: "GA-VERIFIED-002",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getPurchaseHistory).mockResolvedValueOnce({
      items: [
        {
          id: 1,
          order_reference: "cs_test_124",
          package_name: "Starter",
          amount_cents: 20000,
          currency: "USD",
          credits_total: 10,
          entitled_credits_total: 10,
          credits_remaining: 10,
          status: "completed",
          assigned_count: 10,
          unfulfilled_count: 0,
          fulfillment_status: "fulfilled",
          purchased_at: "2026-02-19T00:00:00Z",
          stripe_checkout_session_id: "cs_test_124",
          stripe_payment_intent_id: "pi_test_124",
        },
      ],
    });
    vi.mocked(getFirstPurchaseOfferEligibility).mockResolvedValueOnce({
      eligible: true,
      offer: {
        trigger_package_id: 1,
        offer_package_id: 2,
        offer_package_name: "Starter Plus",
        offer_price_cents: 25000,
        offer_currency: "USD",
        offer_credits_total: 14,
        headline: "First order bonus",
        message: "Upgrade now for extra credits.",
        cta_label: "Upgrade package",
      },
    });
    vi.mocked(createCheckout).mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed",
      response: {
        data: {
          detail: {
            code: "INVENTORY_UNAVAILABLE",
            message: "Add-on inventory unavailable",
          },
        },
      },
    });

    renderRoute("/subscription?checkout=success&session_id=cs_test_124");
    fireEvent.click(await screen.findByRole("button", { name: "Upgrade package" }));
    expect(
      await screen.findByText(
        "Add-on checkout is temporarily unavailable because live inventory is below the required threshold.",
      ),
    ).toBeInTheDocument();
  });

  it("reuses the same checkout retry token across a refresh within the same browser session", async () => {
    window.sessionStorage.clear();

    const { getPackages, createCheckout } = await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getPackages).mockResolvedValue([
      {
        id: 2,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        stripe_price_id: "price_starter_refresh_retry",
        state_limit: 1,
        daily_download_limit: 10,
        features: ["10 leads"],
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getMyLicenses).mockResolvedValue([
      {
        id: 101,
        user_id: 1,
        state: "CA",
        license_number: "CA-VERIFIED-002",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(createCheckout).mockRejectedValue(new Error("checkout unavailable"));

    const initialCheckoutCalls = vi.mocked(createCheckout).mock.calls.length;
    const firstRender = renderRoute("/subscription");
    fireEvent.click(await screen.findByRole("button", { name: "Checkout" }));
    await waitFor(() =>
      expect(vi.mocked(createCheckout).mock.calls.length).toBe(initialCheckoutCalls + 1),
    );
    const firstToken = vi.mocked(createCheckout).mock.calls[initialCheckoutCalls][1];
    expect(typeof firstToken).toBe("string");
    expect(firstToken).toBeTruthy();

    firstRender.unmount();

    renderRoute("/subscription");
    fireEvent.click(await screen.findByRole("button", { name: "Checkout" }));
    await waitFor(() =>
      expect(vi.mocked(createCheckout).mock.calls.length).toBe(initialCheckoutCalls + 2),
    );
    const secondToken = vi.mocked(createCheckout).mock.calls[initialCheckoutCalls + 1][1];
    expect(secondToken).toBe(firstToken);
  });

  it("clears persisted checkout retry tokens after a successful checkout return", async () => {
    window.sessionStorage.clear();

    const { getPackages, createCheckout } = await import("@/api/purchases");
    const { getMyLicenses } = await import("@/api/licenses");
    vi.mocked(getPackages).mockResolvedValue([
      {
        id: 3,
        name: "Pro",
        price_cents: 40000,
        currency: "USD",
        stripe_price_id: "price_pro_retry_clear",
        state_limit: 2,
        daily_download_limit: 20,
        features: ["20 leads"],
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(getMyLicenses).mockResolvedValue([
      {
        id: 102,
        user_id: 1,
        state: "CA",
        license_number: "CA-VERIFIED-003",
        license_type: "Series 65",
        has_document: true,
        verification_status: "verified",
        verified_at: "2026-02-19T00:00:00Z",
        verified_by: 5,
        rejection_reason: null,
        created_at: "2026-02-19T00:00:00Z",
      },
    ]);
    vi.mocked(createCheckout).mockRejectedValue(new Error("checkout unavailable"));

    const initialCheckoutCalls = vi.mocked(createCheckout).mock.calls.length;
    const initialRender = renderRoute("/subscription");
    fireEvent.click(await screen.findByRole("button", { name: "Checkout" }));
    await waitFor(() =>
      expect(vi.mocked(createCheckout).mock.calls.length).toBe(initialCheckoutCalls + 1),
    );

    const tokenKeysBeforeSuccess = Object.keys(window.sessionStorage).filter((storageKey) =>
      storageKey.startsWith("advisor_checkout_retry_token_v1:"),
    );
    expect(tokenKeysBeforeSuccess.length).toBeGreaterThan(0);

    initialRender.unmount();
    renderRoute("/subscription?checkout=success&session_id=cs_test_token_clear");
    await waitFor(() => {
      const tokenKeysAfterSuccess = Object.keys(window.sessionStorage).filter((storageKey) =>
        storageKey.startsWith("advisor_checkout_retry_token_v1:"),
      );
      expect(tokenKeysAfterSuccess).toHaveLength(0);
    });
  });

  it("clears persisted checkout retry tokens after a canceled checkout return", async () => {
    window.sessionStorage.clear();
    window.sessionStorage.setItem(
      "advisor_checkout_retry_token_v1:pkg7",
      JSON.stringify({
        token: "retry_pkg7_fixture",
        expires_at_ms: Date.now() + 60_000,
      }),
    );

    renderRoute("/subscription?checkout=cancel");

    await waitFor(() => {
      const tokenKeysAfterCancel = Object.keys(window.sessionStorage).filter((storageKey) =>
        storageKey.startsWith("advisor_checkout_retry_token_v1:"),
      );
      expect(tokenKeysAfterCancel).toHaveLength(0);
    });
  });
});
