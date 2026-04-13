import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ImportsPage from "@/pages/admin/ImportsPage";

const getAuditLogs = vi.fn();

vi.mock("@/api/admin", () => ({
  getAuditLogs: (...args: unknown[]) => getAuditLogs(...args),
}));

vi.mock("@/components/admin/ImportModal", () => ({
  default: ({ isOpen, onImportSuccess }: { isOpen: boolean; onImportSuccess?: (result: { success: number; failed: number; errors: Array<{ row: number; error: string }> }) => void }) => {
    if (!isOpen) return null;

    return (
      <button
        type="button"
        onClick={() =>
          onImportSuccess?.({
            success: 7,
            failed: 2,
            errors: [
              { row: 3, error: "duplicate mobile_phone" },
              { row: 8, error: "missing state" },
            ],
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

describe("ImportsPage", () => {
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  };

  beforeEach(() => {
    vi.clearAllMocks();

    getAuditLogs.mockResolvedValue({
      items: [
        {
          id: 1,
          actor_user_id: 9,
          action: "lead_bulk_import",
          entity_type: "LeadImport",
          entity_id: null,
          created_at: "2026-02-12T12:30:00Z",
          ip_address: "127.0.0.1",
          meta_data: {
            scanned: 10,
            inserted: 8,
            skipped_duplicates: 1,
            failed: 1,
          },
        },
      ],
      total: 1,
      page: 1,
      size: 10,
    });
  });

  it("renders import history from audit logs", async () => {
    render(<ImportsPage />);

    expect(await screen.findByText("10 rows scanned")).toBeInTheDocument();
    expect(screen.getByText("8 inserted")).toBeInTheDocument();

    expect(getAuditLogs).toHaveBeenCalledWith(
      {
        action: "lead_bulk_import",
        entity_type: "LeadImport",
      },
      1,
      10,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("refreshes history after successful import run", async () => {
    render(<ImportsPage />);

    await screen.findByText("10 rows scanned");

    fireEvent.click(screen.getByRole("button", { name: "Run Import" }));
    fireEvent.click(screen.getByRole("button", { name: "Complete Import" }));

    expect(
      await screen.findByText(
        "Import completed. Inserted 7 leads, 1 duplicates, 2 failed rows.",
      ),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(getAuditLogs).toHaveBeenCalledTimes(2);
    });
  });

  it("ignores stale history responses after a newer import-triggered refresh", async () => {
    const firstHistory = deferred<{
      items: Array<Record<string, unknown>>;
      total: number;
      page: number;
      size: number;
    }>();

    getAuditLogs
      .mockImplementationOnce(() => firstHistory.promise)
      .mockResolvedValueOnce({
        items: [
          {
            id: 2,
            actor_user_id: 9,
            action: "lead_bulk_import",
            entity_type: "LeadImport",
            entity_id: null,
            created_at: "2026-02-13T12:30:00Z",
            ip_address: "127.0.0.1",
            meta_data: {
              scanned: 12,
              inserted: 10,
              skipped_duplicates: 1,
              failed: 1,
            },
          },
        ],
        total: 1,
        page: 1,
        size: 10,
      });

    render(<ImportsPage />);

    fireEvent.click(screen.getByRole("button", { name: "Run Import" }));
    fireEvent.click(screen.getByRole("button", { name: "Complete Import" }));

    expect(await screen.findByText("12 rows scanned")).toBeInTheDocument();

    firstHistory.resolve({
      items: [
        {
          id: 1,
          actor_user_id: 9,
          action: "lead_bulk_import",
          entity_type: "LeadImport",
          entity_id: null,
          created_at: "2026-02-12T12:30:00Z",
          ip_address: "127.0.0.1",
          meta_data: {
            scanned: 10,
            inserted: 8,
            skipped_duplicates: 1,
            failed: 1,
          },
        },
      ],
      total: 1,
      page: 1,
      size: 10,
    });

    await waitFor(() => {
      expect(screen.queryByText("10 rows scanned")).not.toBeInTheDocument();
    });
    expect(screen.getByText("12 rows scanned")).toBeInTheDocument();
  });
});
