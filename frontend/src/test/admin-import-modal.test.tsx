import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ImportModal from "@/components/admin/ImportModal";

const bulkImportLeadsAsAdmin = vi.fn();
const getLeadBulkImportSchemaAsAdmin = vi.fn();

vi.mock("@/api/admin", () => ({
  bulkImportLeadsAsAdmin: (...args: unknown[]) => bulkImportLeadsAsAdmin(...args),
  getLeadBulkImportSchemaAsAdmin: (...args: unknown[]) =>
    getLeadBulkImportSchemaAsAdmin(...args),
}));

const setup = () =>
  render(
    <ImportModal
      isOpen
      onClose={vi.fn()}
      onImportSuccess={vi.fn()}
    />,
  );

const selectFile = (file: File) => {
  const input = document.querySelector('input[type="file"]');
  if (!input) {
    throw new Error("File input not found");
  }
  fireEvent.change(input, { target: { files: [file] } });
};

describe("ImportModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getLeadBulkImportSchemaAsAdmin.mockResolvedValue({
      headers: ["state_code", "zip_code", "mobile_phone"],
      required_values: ["state_code", "mobile_phone"],
      system_fields: {
        source: "csv_import",
      },
    });
  });

  it("renders idle state before a file is selected", async () => {
    setup();

    expect(screen.getByText("Upload CSV file")).toBeInTheDocument();
    expect(await screen.findByText("Header row must exactly match this order:")).toBeInTheDocument();
    expect(screen.getAllByText("state_code").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Run Import" })).toBeDisabled();
  });

  it("shows loading and progress state while import is running", async () => {
    bulkImportLeadsAsAdmin.mockImplementation(() => new Promise(() => {}));

    setup();

    selectFile(new File(["state_code,mobile_phone"], "leads.csv", { type: "text/csv" }));
    fireEvent.click(screen.getByRole("button", { name: "Run Import" }));

    expect(await screen.findByText("Importing...")).toBeInTheDocument();
    expect(screen.getByText("Import Progress")).toBeInTheDocument();
  });

  it("renders in-modal summary after successful import", async () => {
    bulkImportLeadsAsAdmin.mockResolvedValue({
      success: 4,
      failed: 2,
      errors: [
        { row: 2, error: "duplicate mobile_phone" },
        { row: 5, error: "missing state_code" },
      ],
    });

    setup();

    selectFile(new File(["state_code,mobile_phone"], "leads.csv", { type: "text/csv" }));
    fireEvent.click(screen.getByRole("button", { name: "Run Import" }));

    const heading = await screen.findByText("Import Results");
    const summarySection = heading.closest("section");
    expect(summarySection).not.toBeNull();
    expect(summarySection).toHaveTextContent("Inserted");
    expect(summarySection).toHaveTextContent("Failed");
    expect(summarySection).toHaveTextContent("Duplicates");
    expect(summarySection).toHaveTextContent("4");
    expect(summarySection).toHaveTextContent("2");
    expect(summarySection).toHaveTextContent("1");
    expect(
      screen.getByText("Row 2: duplicate mobile_phone"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run Import Again" })).toBeInTheDocument();
  });

  it("shows API failure message", async () => {
    bulkImportLeadsAsAdmin.mockRejectedValue(new Error("import failed"));

    setup();

    selectFile(new File(["state_code,mobile_phone"], "leads.csv", { type: "text/csv" }));
    fireEvent.click(screen.getByRole("button", { name: "Run Import" }));

    await waitFor(() => {
      expect(screen.getByText("import failed")).toBeInTheDocument();
    });
  });
});
