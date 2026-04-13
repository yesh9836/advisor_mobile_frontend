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
      size: 20,
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
    expect(getDashboardStats).toHaveBeenCalledWith(
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    expect(getAuditLogs).toHaveBeenCalledWith(
      {},
      1,
      20,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("shows first 5 recent activity entries and reveals remaining", async () => {
    getAuditLogs.mockResolvedValueOnce({
      items: Array.from({ length: 7 }, (_, index) => ({
        id: index + 1,
        actor_user_id: 8,
        action: `activity_${index + 1}`,
        entity_type: "LeadImport",
        entity_id: 100 + index,
        meta_data: null,
        ip_address: null,
        created_at: `2026-02-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
      })),
      total: 7,
      page: 1,
      size: 20,
    });

    render(
      <MemoryRouter>
        <AdminDashboard />
      </MemoryRouter>,
    );

    expect(await screen.findByText("ACTIVITY 1")).toBeInTheDocument();
    expect(screen.queryByText("ACTIVITY 7")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show Remaining Recent Activity (2)" }));

    expect(screen.getByText("ACTIVITY 7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Recent Activity" })).toBeInTheDocument();
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
      size: 20,
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
