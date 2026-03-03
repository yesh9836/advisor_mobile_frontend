import { render, screen } from "@testing-library/react";
import { AxiosError } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BillingPage from "@/pages/advisor/BillingPage";

vi.mock("@/api/purchases", () => ({
  getPurchaseBillingSummary: vi.fn(),
  getPurchaseHistory: vi.fn(),
}));

const buildPurchaseHistoryItem = (id: number, purchasedAt: string) => ({
  id,
  order_reference: `cs_history_${id}`,
  package_name: `Package ${id}`,
  amount_cents: 10000 + id,
  currency: "USD",
  credits_total: 10,
  entitled_credits_total: 10,
  credits_remaining: 6,
  status: "completed",
  assigned_count: 4,
  unfulfilled_count: 6,
  fulfillment_status: "partially_fulfilled" as const,
  purchased_at: purchasedAt,
  stripe_checkout_session_id: `cs_history_${id}`,
  stripe_payment_intent_id: `pi_history_${id}`,
});

describe("BillingPage resilience", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { getPurchaseBillingSummary, getPurchaseHistory } = await import("@/api/purchases");
    vi.mocked(getPurchaseBillingSummary).mockResolvedValue({
      payment_method: null,
      invoices: [],
      provider_status: "healthy",
      degradation_reason: null,
    });
    vi.mocked(getPurchaseHistory).mockResolvedValue({ items: [] });
  });

  it("renders degraded status note when summary reports degraded provider", async () => {
    const { getPurchaseBillingSummary } = await import("@/api/purchases");
    vi.mocked(getPurchaseBillingSummary).mockResolvedValueOnce({
      payment_method: null,
      provider_status: "degraded",
      degradation_reason: "stripe_unavailable",
      invoices: [
        {
          stripe_invoice_id: "in_degraded_1",
          amount_paid_cents: 15000,
          currency: "USD",
          status: "paid",
          created_at: "2026-03-01T00:00:00Z",
          package_name: "Starter",
          hosted_invoice_url: "https://stripe.example/in_degraded_1",
          invoice_pdf: "https://stripe.example/in_degraded_1.pdf",
          description: "Degraded summary invoice",
        },
      ],
    });

    render(<BillingPage />);

    expect(
      await screen.findByText(
        "Stripe billing details are temporarily unavailable. Showing purchase history.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
  });

  it("falls back to purchase history when summary fails with legacy 502", async () => {
    const { getPurchaseBillingSummary, getPurchaseHistory } = await import("@/api/purchases");
    vi.mocked(getPurchaseBillingSummary).mockRejectedValueOnce(
      Object.assign(new AxiosError("gateway unavailable"), {
        isAxiosError: true,
        response: { status: 502 },
      }),
    );
    vi.mocked(getPurchaseHistory).mockResolvedValueOnce({
      items: [
        buildPurchaseHistoryItem(1, "2026-02-10T00:00:00Z"),
        buildPurchaseHistoryItem(2, "2026-02-12T00:00:00Z"),
      ],
    });

    render(<BillingPage />);

    expect(
      await screen.findByText(
        "Stripe billing details are temporarily unavailable. Showing purchase history.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Package 2")).toBeInTheDocument();
    expect(screen.getAllByText(/Stripe receipt pending/)).toHaveLength(2);
  });

  it("shows error when both summary and history fallback fail", async () => {
    const { getPurchaseBillingSummary, getPurchaseHistory } = await import("@/api/purchases");
    vi.mocked(getPurchaseBillingSummary).mockRejectedValueOnce(new Error("summary failed"));
    vi.mocked(getPurchaseHistory).mockRejectedValueOnce(new Error("history failed"));

    render(<BillingPage />);

    expect(await screen.findByText("history failed")).toBeInTheDocument();
  });
});
