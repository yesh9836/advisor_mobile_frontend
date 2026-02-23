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
  getPurchaseBalance: vi.fn().mockResolvedValue(null),
  getPurchaseHistory: vi.fn().mockResolvedValue({ items: [] }),
  getPurchaseBillingSummary: vi.fn().mockResolvedValue({
    payment_method: null,
    invoices: [],
  }),
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
});
