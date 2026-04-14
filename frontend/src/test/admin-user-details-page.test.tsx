import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UserDetailsPage from "@/pages/admin/UserDetailsPage";

const getUser = vi.fn();
const getUserLicenses = vi.fn();
const getUserPurchaseHistory = vi.fn();
const getUserDownloadHistory = vi.fn();
const getUserRecentActivity = vi.fn();
const deactivateUser = vi.fn();

vi.mock("@/api/admin", () => ({
  getUser: (...args: unknown[]) => getUser(...args),
  getUserLicenses: (...args: unknown[]) => getUserLicenses(...args),
  getUserPurchaseHistory: (...args: unknown[]) => getUserPurchaseHistory(...args),
  getUserDownloadHistory: (...args: unknown[]) => getUserDownloadHistory(...args),
  getUserRecentActivity: (...args: unknown[]) => getUserRecentActivity(...args),
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

const buildUserDetails = () => ({
  id: 7,
  name: "Detail Advisor",
  email: "detail@example.com",
  role: "advisor",
  is_active: true,
  created_at: "2026-02-10T12:00:00Z",
  deactivated_at: null,
  deactivated_by: null,
  credit_summary: {
    total_credits: 20,
    remaining_credits: 12,
    completed_purchases: 2,
  },
  licenses_preview: {
    items: [
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
    total: 1,
    has_more: false,
  },
  purchase_history_preview: {
    items: [
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
    total: 1,
    has_more: false,
  },
  download_history_preview: {
    items: [
      {
        lead_id: 150,
        state_code: "CA",
        downloaded_at: "2026-02-11T00:00:00Z",
        csv_batch_id: "batch-1",
      },
    ],
    total: 1,
    has_more: false,
  },
  recent_activity_preview: {
    items: [
      {
        id: 810,
        actor_user_id: 7,
        actor_name: "Detail Advisor",
        actor_email: "detail@example.com",
        action: "lead_downloaded",
        entity_type: "Lead",
        entity_id: 150,
        meta_data: { state: "CA" },
        ip_address: "203.0.113.20",
        created_at: "2026-02-11T00:00:00Z",
      },
    ],
    total: 1,
    has_more: false,
  },
});

describe("UserDetailsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getUser.mockResolvedValue(buildUserDetails());
    getUserLicenses.mockResolvedValue({ items: [], total: 0, page: 1, size: 20 });
    getUserPurchaseHistory.mockResolvedValue({ items: [], total: 0, page: 1, size: 20 });
    getUserDownloadHistory.mockResolvedValue({ items: [], total: 0, page: 1, size: 20 });
    getUserRecentActivity.mockResolvedValue({ items: [], total: 0, page: 1, size: 20 });
    deactivateUser.mockResolvedValue(undefined);
  });

  it("renders bounded preview sections from the summary response", async () => {
    getUser.mockResolvedValueOnce({
      ...buildUserDetails(),
      licenses_preview: {
        items: Array.from({ length: 5 }, (_, index) => ({
          id: 2000 + index,
          state: "CA",
          license_number: `LIC-${1000 + index}`,
          license_type: "resident",
          verification_status: "verified",
          created_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
          verified_at: `2026-02-${String(index + 1).padStart(2, "0")}T12:00:00Z`,
          rejection_reason: null,
        })),
        total: 12,
        has_more: true,
      },
      purchase_history_preview: {
        items: Array.from({ length: 5 }, (_, index) => ({
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
        total: 12,
        has_more: true,
      },
      download_history_preview: {
        items: Array.from({ length: 5 }, (_, index) => ({
          lead_id: 1000 + index,
          state_code: "CA",
          downloaded_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
          csv_batch_id: `batch-${index + 1}`,
        })),
        total: 12,
        has_more: true,
      },
      recent_activity_preview: {
        items: Array.from({ length: 5 }, (_, index) => ({
          id: 900 + index,
          actor_user_id: 7,
          actor_name: "Detail Advisor",
          actor_email: "detail@example.com",
          action: `activity_${index + 1}`,
          entity_type: "Lead",
          entity_id: 5000 + index,
          meta_data: null,
          ip_address: null,
          created_at: `2026-02-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
        })),
        total: 12,
        has_more: true,
      },
    });

    renderPage();

    expect(await screen.findByText("Detail Advisor")).toBeInTheDocument();
    expect(screen.getByText("order-1000")).toBeInTheDocument();
    expect(screen.queryByText("order-1011")).not.toBeInTheDocument();
    expect(screen.getByText("CA • LIC-1000")).toBeInTheDocument();
    expect(screen.queryByText("CA • LIC-1011")).not.toBeInTheDocument();
    expect(screen.getByText("1000")).toBeInTheDocument();
    expect(screen.queryByText("1011")).not.toBeInTheDocument();
    expect(screen.getByText("Affected: Lead #5000")).toBeInTheDocument();
    expect(screen.queryByText("Affected: Lead #5011")).not.toBeInTheDocument();
    expect(screen.getAllByText("Performed by: Detail Advisor • detail@example.com")).toHaveLength(5);
    expect(screen.getByText("Performed activity 1.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Full Purchase History (7 more)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Full Licenses (7 more)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Full Download History (7 more)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View Full Recent Activity (7 more)" })).toBeInTheDocument();
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

  it("loads full purchase history on demand and paginates additional pages", async () => {
    getUser.mockResolvedValueOnce({
      ...buildUserDetails(),
      purchase_history_preview: {
        items: Array.from({ length: 5 }, (_, index) => ({
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
        total: 25,
        has_more: true,
      },
    });

    getUserPurchaseHistory.mockResolvedValueOnce({
      items: Array.from({ length: 20 }, (_, index) => ({
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
      total: 25,
      page: 1,
      size: 20,
    });
    getUserPurchaseHistory.mockResolvedValueOnce({
      items: Array.from({ length: 5 }, (_, index) => ({
        id: 3020 + index,
        order_reference: `order-${1020 + index}`,
        status: "completed",
        package_name: "Starter Pack",
        amount_cents: 15000,
        currency: "USD",
        credits_total: 10,
        credits_remaining: 4,
        purchased_at: `2026-03-${String(index + 1).padStart(2, "0")}T00:00:00Z`,
      })),
      total: 25,
      page: 2,
      size: 20,
    });

    renderPage();

    await screen.findByText("Detail Advisor");

    expect(screen.getByText("order-1000")).toBeInTheDocument();
    expect(screen.queryByText("order-1019")).not.toBeInTheDocument();
    expect(screen.queryByText("order-1024")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "View Full Purchase History (20 more)" }));

    await waitFor(() => {
      expect(getUserPurchaseHistory).toHaveBeenCalledWith(7, 1, 20);
    });

    expect(await screen.findByText("order-1019")).toBeInTheDocument();
    expect(screen.getByText("Showing 20 of 25 purchase records.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load More Purchases" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Load More Purchases" }));

    await waitFor(() => {
      expect(getUserPurchaseHistory).toHaveBeenCalledWith(7, 2, 20);
    });

    expect(await screen.findByText("order-1024")).toBeInTheDocument();
    expect(screen.getByText("Showing 25 of 25 purchase records.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show Less Purchase History" })).toBeInTheDocument();
  });

  it("shows invalid id state for malformed route params", async () => {
    renderPage("/admin/users/invalid");

    expect(await screen.findByText("Invalid user ID.")).toBeInTheDocument();
    expect(getUser).not.toHaveBeenCalled();
  });
});
