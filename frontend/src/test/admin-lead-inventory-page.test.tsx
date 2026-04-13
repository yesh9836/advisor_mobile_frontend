import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import LeadInventoryPage from "@/pages/admin/LeadInventoryPage";

const getLeadInventory = vi.fn();
const getLicenseStatusSummary = vi.fn();
const createLeadAsAdmin = vi.fn();

vi.mock("@/api/admin", () => ({
  getLeadInventory: (...args: unknown[]) => getLeadInventory(...args),
  getLicenseStatusSummary: (...args: unknown[]) => getLicenseStatusSummary(...args),
  createLeadAsAdmin: (...args: unknown[]) => createLeadAsAdmin(...args),
}));

vi.mock("@/components/admin/ImportModal", () => ({
  default: ({ isOpen, onImportSuccess }: { isOpen: boolean; onImportSuccess?: (result: { success: number; failed: number; errors: Array<{ row: number; error: string }> }) => void }) => {
    if (!isOpen) return null;

    return (
      <button
        type="button"
        onClick={() =>
          onImportSuccess?.({
            success: 4,
            failed: 1,
            errors: [{ row: 2, error: "duplicate mobile_phone" }],
          })
        }
      >
        Complete Import
      </button>
    );
  },
  toImportSummary: (result: { success: number; failed: number; errors: Array<{ error: string }> }) => ({
    inserted: result.success,
    failed: result.failed,
    duplicateCount: result.errors.filter((entry) =>
      entry.error.toLowerCase().includes("duplicate"),
    ).length,
  }),
}));

describe("LeadInventoryPage", () => {
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  };

  beforeEach(() => {
    vi.clearAllMocks();

    getLeadInventory.mockResolvedValue({
      items: [
        {
          id: 101,
          state_code: "CA",
          first_name: "Alice",
          last_name: "North",
          mobile_phone: "555-111-0000",
          source: "manual_entry",
          created_at: "2026-02-10T12:00:00Z",
          download_count: 0,
          assigned_advisor_id: null,
          assigned_advisor_name: null,
          assigned_advisor_email: null,
          purchase_id: null,
          purchase_reference: null,
        },
      ],
      total: 1,
      page: 1,
      size: 20,
    });

    getLicenseStatusSummary.mockResolvedValue([
      { status: "pending", count: 2 },
      { status: "verified", count: 5 },
      { status: "rejected", count: 1 },
    ]);

    createLeadAsAdmin.mockResolvedValue({ id: 999 });
  });

  it("renders inventory rows and license status summary", async () => {
    render(<LeadInventoryPage />);

    expect(await screen.findByText("Alice North")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("verified")).toBeInTheDocument();
    expect(screen.getByText("rejected")).toBeInTheDocument();

    expect(getLeadInventory).toHaveBeenCalledWith(
      1,
      20,
      expect.any(Object),
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("applies search filters and requests updated inventory", async () => {
    render(<LeadInventoryPage />);

    await screen.findByText("Alice North");

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "alice" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));

    await waitFor(() => {
      expect(getLeadInventory).toHaveBeenLastCalledWith(
        1,
        20,
        expect.objectContaining({ search: "alice" }),
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });
  });

  it("creates a lead and shows success state", async () => {
    render(<LeadInventoryPage />);

    await screen.findByText("Alice North");

    fireEvent.click(screen.getByRole("button", { name: "Add Lead" }));

    fireEvent.change(screen.getByLabelText("State", { selector: "#lead-state" }), {
      target: { value: "CA" },
    });
    fireEvent.change(screen.getByLabelText("Mobile Phone", { selector: "#lead-phone" }), {
      target: { value: "555-222-3333" },
    });
    fireEvent.change(screen.getByLabelText("First Name", { selector: "#lead-first-name" }), {
      target: { value: "New" },
    });
    fireEvent.change(screen.getByLabelText("Last Name", { selector: "#lead-last-name" }), {
      target: { value: "Lead" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create Lead" }));

    await waitFor(() => {
      expect(createLeadAsAdmin).toHaveBeenCalledWith(
        expect.objectContaining({
          state_code: "CA",
          mobile_phone: "555-222-3333",
          first_name: "New",
          last_name: "Lead",
        }),
      );
    });

    expect(await screen.findByText("Lead created successfully.")).toBeInTheDocument();
  });

  it("reports import success when modal callback completes", async () => {
    render(<LeadInventoryPage />);

    await screen.findByText("Alice North");

    fireEvent.click(screen.getByRole("button", { name: "Import Leads" }));
    fireEvent.click(screen.getByRole("button", { name: "Complete Import" }));

    expect(
      await screen.findByText(
        "Import completed. Inserted 4 leads, 1 duplicates, 1 failed rows.",
      ),
    ).toBeInTheDocument();
  });

  it("ignores stale inventory responses after filters change quickly", async () => {
    const firstInventory = deferred<{
      items: Array<Record<string, unknown>>;
      total: number;
      page: number;
      size: number;
    }>();
    const firstSummary = deferred<Array<{ status: "pending" | "verified" | "rejected"; count: number }>>();

    getLeadInventory
      .mockImplementationOnce(() => firstInventory.promise)
      .mockResolvedValueOnce({
        items: [
          {
            id: 202,
            state_code: "TX",
            first_name: "Fresh",
            last_name: "Result",
            mobile_phone: "555-222-0000",
            source: "manual_entry",
            created_at: "2026-02-11T12:00:00Z",
            download_count: 0,
            assigned_advisor_id: null,
            assigned_advisor_name: null,
            assigned_advisor_email: null,
            purchase_id: null,
            purchase_reference: null,
          },
        ],
        total: 1,
        page: 1,
        size: 20,
      });
    getLicenseStatusSummary
      .mockImplementationOnce(() => firstSummary.promise)
      .mockResolvedValueOnce([
        { status: "pending", count: 1 },
        { status: "verified", count: 0 },
        { status: "rejected", count: 0 },
      ]);

    render(<LeadInventoryPage />);

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: "fresh" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));

    expect(await screen.findByText("Fresh Result")).toBeInTheDocument();

    firstInventory.resolve({
      items: [
        {
          id: 101,
          state_code: "CA",
          first_name: "Stale",
          last_name: "Result",
          mobile_phone: "555-111-0000",
          source: "manual_entry",
          created_at: "2026-02-10T12:00:00Z",
          download_count: 0,
          assigned_advisor_id: null,
          assigned_advisor_name: null,
          assigned_advisor_email: null,
          purchase_id: null,
          purchase_reference: null,
        },
      ],
      total: 1,
      page: 1,
      size: 20,
    });
    firstSummary.resolve([
      { status: "pending", count: 9 },
      { status: "verified", count: 0 },
      { status: "rejected", count: 0 },
    ]);

    await waitFor(() => {
      expect(screen.queryByText("Stale Result")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Fresh Result")).toBeInTheDocument();
  });
});
