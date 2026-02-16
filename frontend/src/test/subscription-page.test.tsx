import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SubscriptionPage from "@/pages/advisor/SubscriptionPage";

vi.mock("@/api/purchases", () => ({
  getPackages: vi.fn().mockResolvedValue([]),
  createCheckout: vi.fn(),
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
      screen.getByText(/Checkout completed\. Your lead credits are available/),
    ).toBeInTheDocument();
    expect(await screen.findByText("No Packages Available")).toBeInTheDocument();
  });

  it("shows cancel notice when redirected from Stripe cancel URL", async () => {
    renderRoute("/subscription?checkout=cancel");

    expect(
      screen.getByText("Checkout canceled. No charge was made."),
    ).toBeInTheDocument();
    expect(await screen.findByText("No Packages Available")).toBeInTheDocument();
  });
});
