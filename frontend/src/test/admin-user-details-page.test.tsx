import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserDetailsPage from "@/pages/admin/UserDetailsPage";

const getUser = vi.fn();
const deactivateUser = vi.fn();

vi.mock("@/api/admin", () => ({
  getUser: (...args: unknown[]) => getUser(...args),
  deactivateUser: (...args: unknown[]) => deactivateUser(...args),
}));

const renderPage = (path = "/admin/users/7") => {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/admin/users/:userId" element={<UserDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("UserDetailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getUser.mockResolvedValue({
      id: 7,
      name: "Detail Advisor",
      email: "detail@example.com",
      role: "advisor",
      is_active: true,
      created_at: "2026-02-10T12:00:00Z",
      deactivated_at: null,
      deactivated_by: null,
      licenses: [
        {
          id: 91,
          state: "CA",
          license_number: "CA-1234",
          license_type: "resident",
          verification_status: "verified",
          created_at: "2026-02-01T00:00:00Z",
          verified_at: "2026-02-03T00:00:00Z",
          rejection_reason: null,
        },
      ],
      credit_summary: {
        total_credits: 20,
        remaining_credits: 12,
        completed_purchases: 2,
      },
      purchase_history: [
        {
          id: 12,
          order_reference: "cs_test_purchase_1",
          status: "completed",
          package_name: "Starter Pack",
          amount_cents: 15000,
          currency: "USD",
          credits_total: 10,
          credits_remaining: 4,
          purchased_at: "2026-02-01T00:00:00Z",
        },
      ],
      download_history: [
        {
          lead_id: 150,
          state_code: "CA",
          downloaded_at: "2026-02-11T00:00:00Z",
          csv_batch_id: "batch-1",
        },
      ],
      recent_activity: [
        {
          id: 810,
          actor_user_id: 7,
          action: "lead_downloaded",
          entity_type: "Lead",
          entity_id: 150,
          meta_data: { state: "CA" },
          ip_address: "203.0.113.20",
          created_at: "2026-02-11T00:00:00Z",
        },
      ],
    });

    deactivateUser.mockResolvedValue(undefined);
  });

  it("renders user details sections", async () => {
    renderPage();

    expect(await screen.findByText("Detail Advisor")).toBeInTheDocument();
    expect(screen.getByText("detail@example.com")).toBeInTheDocument();
    expect(screen.getByText("CA • CA-1234")).toBeInTheDocument();
    expect(screen.getByText("Starter Pack")).toBeInTheDocument();
    expect(screen.getByText("LEAD DOWNLOADED")).toBeInTheDocument();
  });

  it("deactivates active users and reloads details", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    renderPage();

    await screen.findByText("Detail Advisor");

    fireEvent.change(screen.getByLabelText("Deactivation reason (optional)"), {
      target: { value: "Fraud review" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Deactivate User" }));

    await waitFor(() => {
      expect(deactivateUser).toHaveBeenCalledWith(7, "Fraud review");
    });

    expect(getUser).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("User deactivated successfully.")).toBeInTheDocument();

    confirmSpy.mockRestore();
  });

  it("shows first 5 records per history section and reveals remaining records", async () => {
    getUser.mockResolvedValueOnce({
      id: 7,
      name: "Detail Advisor",
      email: "detail@example.com",
      role: "advisor",
      is_active: true,
      created_at: "2026-02-10T12:00:00Z",
      deactivated_at: null,
      deactivated_by: null,
      licenses: Array.from({ length: 12 }, (_, index) => ({
        id: 2000 + index,
        state: "CA",
        license_number: `LIC-${1000 + index}`,
        license_type: "resident",
        verification_status: "verified",
        created_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
        verified_at: `2026-02-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
        rejection_reason: null,
      })),
      credit_summary: {
        total_credits: 20,
        remaining_credits: 12,
        completed_purchases: 2,
      },
      purchase_history: Array.from({ length: 12 }, (_, index) => ({
        id: 3000 + index,
        order_reference: `order-${1000 + index}`,
        status: "completed",
        package_name: "Starter Pack",
        amount_cents: 15000,
        currency: "USD",
        credits_total: 10,
        credits_remaining: 4,
        purchased_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
      })),
      download_history: Array.from({ length: 12 }, (_, index) => ({
        lead_id: 1000 + index,
        state_code: "CA",
        downloaded_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
        csv_batch_id: `batch-${index + 1}`,
      })),
      recent_activity: Array.from({ length: 12 }, (_, index) => ({
        id: 900 + index,
        actor_user_id: 7,
        action: `activity_${index + 1}`,
        entity_type: "Lead",
        entity_id: 5000 + index,
        meta_data: null,
        ip_address: null,
        created_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
      })),
    });

    renderPage();

    await screen.findByText("Detail Advisor");

    expect(screen.getByText("order-1000")).toBeInTheDocument();
    expect(screen.queryByText("order-1011")).not.toBeInTheDocument();
    expect(screen.getByText("CA • LIC-1000")).toBeInTheDocument();
    expect(screen.queryByText("CA • LIC-1011")).not.toBeInTheDocument();
    expect(screen.getByText("1000")).toBeInTheDocument();
    expect(screen.queryByText("1011")).not.toBeInTheDocument();
    expect(screen.getByText("Entity: Lead #5000")).toBeInTheDocument();
    expect(screen.queryByText("Entity: Lead #5011")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show Remaining Purchase History (7)" }));
    fireEvent.click(screen.getByRole("button", { name: "Show Remaining Licenses (7)" }));
    fireEvent.click(screen.getByRole("button", { name: "Show Remaining Download History (7)" }));
    fireEvent.click(screen.getByRole("button", { name: "Show Remaining Recent Activity (7)" }));

    expect(screen.getByText("order-1011")).toBeInTheDocument();
    expect(screen.getByText("CA • LIC-1011")).toBeInTheDocument();
    expect(screen.getByText("1011")).toBeInTheDocument();
    expect(screen.getByText("Entity: Lead #5011")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Purchase History" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Licenses" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Download History" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Recent Activity" })).toBeInTheDocument();
  });

  it("shows invalid id state for malformed route params", async () => {
    renderPage("/admin/users/invalid");

    expect(await screen.findByText("Invalid user ID.")).toBeInTheDocument();
    expect(getUser).not.toHaveBeenCalled();
  });
});
