import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminDashboard from "@/pages/admin/AdminDashboard";

const getDashboardStats = vi.fn();
const getAuditLogs = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/api/admin", () => ({
  getDashboardStats: (...args: unknown[]) => getDashboardStats(...args),
  getAuditLogs: (...args: unknown[]) => getAuditLogs(...args),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );

  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe("AdminDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getDashboardStats.mockResolvedValue({
      total_users: 10,
      completed_purchases: 6,
      advisors_with_credits: 4,
      pending_licenses: 3,
      total_leads: 21,
      total_revenue_cents: 120000,
      currency: "USD",
    });

    getAuditLogs.mockResolvedValue({
      items: [
        {
          id: 1,
          actor_user_id: 8,
          action: "lead_bulk_import",
          entity_type: "LeadImport",
          entity_id: 4,
          meta_data: null,
          ip_address: null,
          created_at: "2026-02-13T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      size: 6,
    });
  });

  it("renders stats and recent activity on success", async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("10")).toBeInTheDocument();
    expect(screen.getByText("LEAD BULK IMPORT")).toBeInTheDocument();
    expect(getAuditLogs).toHaveBeenCalledWith({}, 1, 6);
  });

  it("shows loading state before data resolves", async () => {
    getDashboardStats.mockImplementation(() => new Promise(() => {}));
    getAuditLogs.mockImplementation(() => new Promise(() => {}));

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText("Loading recent activity...")).toBeInTheDocument();
    expect(screen.getAllByText("...").length).toBeGreaterThan(0);
  });

  it("shows empty activity state", async () => {
    getAuditLogs.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      size: 6,
    });

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("No recent activity found.")).toBeInTheDocument();
  });

  it("shows API failure states independently", async () => {
    getDashboardStats.mockRejectedValue(new Error("stats failed"));
    getAuditLogs.mockRejectedValue(new Error("activity failed"));

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("stats failed")).toBeInTheDocument();
    expect(await screen.findByText("activity failed")).toBeInTheDocument();
  });

  it("navigates to license reviews when pending approvals is clicked", async () => {
    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    const pendingButton = await screen.findByRole("button", {
      name: "Pending approvals",
    });
    fireEvent.click(pendingButton);

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith("/admin/license-reviews");
    });
  });
});
