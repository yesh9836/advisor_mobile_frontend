import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SubscriptionPage from "@/pages/advisor/SubscriptionPage";

vi.mock("@/api/purchases", () => ({
  getPackages: vi.fn().mockResolvedValue([]),
  createCheckout: vi.fn(),
  getPurchaseHistory: vi.fn().mockResolvedValue({
    items: [],
  }),
}));

vi.mock("@/api/licenses", () => ({
  getMyLicenses: vi.fn().mockResolvedValue([]),
}));

const renderRoute = (route: string) => {
  render(
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
});
