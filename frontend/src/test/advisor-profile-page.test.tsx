import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ProfilePage from "@/pages/advisor/ProfilePage";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "advisor.profile@example.com",
      name: "Advisor Profile",
      phone: "555-111-2222",
      role: "advisor",
      stripe_customer_id: null,
      created_at: "2026-01-01T00:00:00Z",
    },
  }),
}));

vi.mock("@/api/purchases", () => ({
  getPurchaseBalance: vi.fn().mockResolvedValue({
    total_credits: 20,
    remaining_credits: 14,
    completed_purchases: 2,
  }),
  getPurchaseHistory: vi.fn().mockResolvedValue({
    items: [
      {
        id: 101,
        order_reference: "cs_profile_101",
        package_name: "Starter",
        amount_cents: 20000,
        currency: "USD",
        credits_total: 10,
        entitled_credits_total: 10,
        credits_remaining: 8,
        status: "completed",
        assigned_count: 6,
        unfulfilled_count: 4,
        fulfillment_status: "partially_fulfilled",
        purchased_at: "2026-02-18T00:00:00Z",
        stripe_checkout_session_id: "cs_profile_101",
        stripe_payment_intent_id: "pi_profile_101",
      },
      {
        id: 102,
        order_reference: "cs_profile_102",
        package_name: "Pro",
        amount_cents: 35000,
        currency: "USD",
        credits_total: 10,
        entitled_credits_total: 10,
        credits_remaining: 6,
        status: "completed",
        assigned_count: 10,
        unfulfilled_count: 0,
        fulfillment_status: "fulfilled",
        purchased_at: "2026-02-17T00:00:00Z",
        stripe_checkout_session_id: "cs_profile_102",
        stripe_payment_intent_id: "pi_profile_102",
      },
    ],
  }),
}));

vi.mock("@/components/license/LicenseForm", () => ({
  default: () => <div data-testid="license-form">LicenseForm</div>,
}));

vi.mock("@/components/license/LicenseList", () => ({
  default: () => <div data-testid="license-list">LicenseList</div>,
}));

describe("ProfilePage purchase fulfillment summary", () => {
  it("renders pending auto-delivery and latest purchase fulfillment details", async () => {
    render(<ProfilePage />);

    expect(
      await screen.findByText((_, element) =>
        element?.tagName === "P"
        && (element.textContent || "").replace(/\s+/g, " ").trim() === "Pending auto-delivery leads: 4",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Delivered now:")).toBeInTheDocument();
    expect(screen.getByText("6/10")).toBeInTheDocument();
    expect(screen.getByText("Pending auto-delivery:")).toBeInTheDocument();
    expect(screen.getByText("Fulfillment:")).toBeInTheDocument();
    expect(screen.getByText("Partially fulfilled")).toBeInTheDocument();
    expect(
      screen.getByText(
        "New leads are assigned automatically when inventory is available in your licensed states.",
      ),
    ).toBeInTheDocument();
  });

  it("shows latest completed purchase even when newest purchase is still pending", async () => {
    const { getPurchaseHistory } = await import("@/api/purchases");
    vi.mocked(getPurchaseHistory).mockResolvedValueOnce({
      items: [
        {
          id: 201,
          order_reference: "cs_profile_201",
          package_name: "First Purchase Add-on",
          amount_cents: 1000,
          currency: "USD",
          credits_total: 5,
          entitled_credits_total: 5,
          credits_remaining: 0,
          status: "pending",
          assigned_count: 0,
          unfulfilled_count: 0,
          fulfillment_status: "pending",
          purchased_at: "2026-02-20T00:00:00Z",
          stripe_checkout_session_id: "cs_profile_201",
          stripe_payment_intent_id: "pi_profile_201",
        },
        {
          id: 200,
          order_reference: "cs_profile_200",
          package_name: "Starter",
          amount_cents: 20000,
          currency: "USD",
          credits_total: 10,
          entitled_credits_total: 10,
          credits_remaining: 8,
          status: "completed",
          assigned_count: 6,
          unfulfilled_count: 4,
          fulfillment_status: "partially_fulfilled",
          purchased_at: "2026-02-19T00:00:00Z",
          stripe_checkout_session_id: "cs_profile_200",
          stripe_payment_intent_id: "pi_profile_200",
        },
      ],
    });

    render(<ProfilePage />);

    expect(
      await screen.findByText(/Latest completed purchase:/),
    ).toBeInTheDocument();
    expect(screen.getByText(/Starter on/)).toBeInTheDocument();
    expect(screen.queryByText(/First Purchase Add-on on/)).not.toBeInTheDocument();
  });
});
