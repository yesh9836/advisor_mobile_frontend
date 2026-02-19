import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Outlet } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AppRoutes } from "@/routes";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: {
      id: 3,
      email: "admin@example.com",
      name: "Admin User",
      phone: "555-123-4567",
      role: "admin",
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

vi.mock("@/components/auth/ProtectedRoute", () => ({
  default: ({ children }: { children?: ReactNode }) => {
    return children ? <>{children}</> : <Outlet />;
  },
}));

vi.mock("@/components/layout/Layout", () => ({
  default: () => <Outlet />,
}));

vi.mock("@/pages/admin/AdminDashboard", () => ({
  default: () => <div>Admin Dashboard Route</div>,
}));

vi.mock("@/pages/admin/LeadInventoryPage", () => ({
  default: () => <div>Lead Inventory Route</div>,
}));

vi.mock("@/pages/admin/UsersPage", () => ({
  default: () => <div>Users Route</div>,
}));

vi.mock("@/pages/admin/UserDetailsPage", () => ({
  default: () => <div>User Details Route</div>,
}));

vi.mock("@/pages/admin/OrdersPage", () => ({
  default: () => <div>Orders Route</div>,
}));

vi.mock("@/pages/admin/ImportsPage", () => ({
  default: () => <div>Imports Route</div>,
}));

vi.mock("@/pages/admin/AnalyticsPage", () => ({
  default: () => <div>Analytics Route</div>,
}));

vi.mock("@/pages/admin/FirstPurchaseOfferPage", () => ({
  default: () => <div>First Purchase Offer Route</div>,
}));

vi.mock("@/pages/admin/LicenseReviewsPage", () => ({
  default: () => <div>License Reviews Route</div>,
}));

const renderRoute = (route: string) => {
  render(
    <MemoryRouter initialEntries={[route]}>
      <AppRoutes />
    </MemoryRouter>,
  );
};

describe("Admin user route mapping", () => {
  it("maps /admin/users to UsersPage", async () => {
    renderRoute("/admin/users");
    expect(await screen.findByText("Users Route")).toBeInTheDocument();
  });

  it("maps /admin/users/:userId to UserDetailsPage", async () => {
    renderRoute("/admin/users/99");
    expect(await screen.findByText("User Details Route")).toBeInTheDocument();
  });

  it("maps /admin/analytics to AnalyticsPage", async () => {
    renderRoute("/admin/analytics");
    expect(await screen.findByText("Analytics Route")).toBeInTheDocument();
  });

  it("maps /admin/first-purchase-offer to FirstPurchaseOfferPage", async () => {
    renderRoute("/admin/first-purchase-offer");
    expect(await screen.findByText("First Purchase Offer Route")).toBeInTheDocument();
  });
});
