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
