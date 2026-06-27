import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppRoutes } from "@/routes";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      email: "advisor@example.com",
      name: "Advisor User",
      phone: "555-123-4567",
      role: "advisor",
      stripe_customer_id: null,
      created_at: "2026-01-01T00:00:00Z",
    },
    loading: false,
    error: null,
    isAuthenticated: true,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    clearError: vi.fn(),
  }),
}));

vi.mock("@/api/purchases", () => ({
  createCheckout: vi.fn().mockResolvedValue({
    session_id: "cs_test",
    url: "https://checkout.example.test",
  }),
  getPackages: vi.fn().mockResolvedValue([]),
  getPurchaseBalance: vi.fn().mockResolvedValue(null),
  getPurchaseHistory: vi.fn().mockResolvedValue({ items: [] }),
  getPurchaseBillingSummary: vi.fn().mockResolvedValue({
    payment_method: null,
    invoices: [],
  }),
}));

vi.mock("@/api/goals", () => ({
  getMyGoal: vi.fn().mockResolvedValue({
    goal: {
      id: 1,
      user_id: 1,
      target_year: 2026,
      annual_income_goal_cents: 25_000_000,
      average_commission_cents: 350_000,
      earned_ytd_cents: 7_800_000,
      appointment_to_deal_rate_bps: 1_200,
      lead_to_appointment_rate_bps: 2_500,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
    },
    derived: {
      deals_needed: 72,
      appointments_needed: 600,
      leads_needed: 2400,
      closed_deals_ytd: 0,
      income_progress_percent: 31,
      deals_remaining: 50,
      appointments_remaining: 417,
      leads_remaining: 1668,
      recommended_monthly_leads: 239,
      pacing: {
        remaining_months: 7,
        recommended_monthly_leads: 239,
        status: "active",
        message: "Buy about 239 leads/month for the rest of the year.",
      },
    },
    packages: [],
  }),
  saveMyGoal: vi.fn(),
}));

vi.mock("@/components/auth/ProtectedRoute", () => ({
  default: ({ children }: { children?: ReactNode }) => {
    return children ? <>{children}</> : <Outlet />;
  },
}));

vi.mock("@/components/layout/Layout", () => ({
  default: () => <Outlet />,
}));

vi.mock("@/components/license/LicenseForm", () => ({
  default: () => <div data-testid="license-form">LicenseForm</div>,
}));

vi.mock("@/components/license/LicenseList", () => ({
  default: () => <div data-testid="license-list">LicenseList</div>,
}));

const renderRoute = (route: string) => {
  render(
    <MemoryRouter initialEntries={[route]}>
      <AppRoutes />
    </MemoryRouter>,
  );
};

describe("AppRoutes advisor page mapping", () => {
  it("renders profile and license workflow at /profile", async () => {
    renderRoute("/profile");

    expect(
      await screen.findByRole("heading", { name: "Advisor Profile" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("license-form")).toBeInTheDocument();
    expect(screen.getByTestId("license-list")).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Billing" }),
    ).not.toBeInTheDocument();
    expect(
      await screen.findByText("No completed purchases found."),
    ).toBeInTheDocument();
  });

  it("renders billing workflow at /billing", async () => {
    renderRoute("/billing");

    expect(await screen.findByRole("heading", { name: "Billing" })).toBeInTheDocument();
    expect(
      screen.getByText("Invoices and purchase history."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Advisor Profile" }),
    ).not.toBeInTheDocument();
    expect(await screen.findByText("No invoices yet.")).toBeInTheDocument();
  });

  it("renders advisor goals workflow at /goals", async () => {
    renderRoute("/goals");

    expect(await screen.findByRole("heading", { name: "Goals" })).toBeInTheDocument();
    expect(await screen.findByText("Recommended Lead Volume")).toBeInTheDocument();
  });
});
