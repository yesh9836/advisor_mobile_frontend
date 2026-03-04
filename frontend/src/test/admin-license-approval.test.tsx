import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  approveLicense,
  downloadLicenseDocument,
  getPendingLicenses,
  getProcessedLicenses,
  previewLicenseDocument,
  rejectLicense,
} from "@/api/admin";
import LicenseApproval from "@/components/admin/LicenseApproval";
import type { AdminLicenseDecisionRow, LicenseWithUser } from "@/types/license";

vi.mock("@/api/admin", () => ({
  getPendingLicenses: vi.fn(),
  getProcessedLicenses: vi.fn(),
  approveLicense: vi.fn(),
  rejectLicense: vi.fn(),
  downloadLicenseDocument: vi.fn(),
  previewLicenseDocument: vi.fn(),
}));

const pendingLicense: LicenseWithUser = {
  id: 101,
  user_id: 44,
  user_name: "Jane Advisor",
  user_email: "jane.advisor@example.com",
  state: "CA",
  license_number: "CA-LIC-9001",
  license_type: "Series 65",
  has_document: true,
  verification_status: "pending",
  verified_at: null,
  verified_by: null,
  rejection_reason: null,
  created_at: "2026-02-10T15:42:00Z",
};

const processedLicense: AdminLicenseDecisionRow = {
  license_id: 202,
  user_id: 45,
  user_name: "Existing Advisor",
  user_email: "existing.advisor@example.com",
  state: "NV",
  license_number: "NV-LIC-2200",
  license_type: "Series 63",
  decision_status: "verified",
  decision_at: "2026-02-10T11:12:00Z",
  submission_type: "first_time",
  review_cycle: 1,
  rejection_reason: null,
  created_at: "2026-02-08T10:00:00Z",
};

const buildProcessedDecision = (index: number): AdminLicenseDecisionRow => ({
  ...processedLicense,
  license_id: 300 + index,
  user_id: 600 + index,
  user_name: `Processed Advisor ${index}`,
  user_email: `processed.advisor.${index}@example.com`,
  state: "CA",
  license_number: `CA-LIC-${9000 + index}`,
  decision_at: `2026-02-${String(index).padStart(2, "0")}T11:12:00Z`,
  created_at: `2026-02-${String(index).padStart(2, "0")}T10:00:00Z`,
});

describe("LicenseApproval", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(URL, "createObjectURL", {
      writable: true,
      value: vi.fn(() => "blob:license-document"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      writable: true,
      value: vi.fn(),
    });
    Object.defineProperty(HTMLAnchorElement.prototype, "click", {
      writable: true,
      value: vi.fn(),
    });

    vi.mocked(getPendingLicenses).mockResolvedValue([pendingLicense]);
    vi.mocked(getProcessedLicenses).mockResolvedValue([processedLicense]);
    vi.mocked(approveLicense).mockResolvedValue({
      ...pendingLicense,
      verification_status: "verified",
      verified_at: "2026-02-10T16:00:00Z",
      verified_by: 1,
    });
    vi.mocked(rejectLicense).mockResolvedValue({
      ...pendingLicense,
      verification_status: "rejected",
      rejection_reason: "Invalid document",
    });
    vi.mocked(downloadLicenseDocument).mockResolvedValue({
      blob: new Blob(["license-pdf"], { type: "application/pdf" }),
      filename: "license_101.pdf",
    });
    vi.mocked(previewLicenseDocument).mockResolvedValue({
      blob: new Blob(["%PDF-1.4 preview"], { type: "application/pdf" }),
      contentType: "application/pdf",
    });
  });

  it("renders pending licenses", async () => {
    render(<LicenseApproval />);

    expect(
      await screen.findByRole("heading", { name: "Pending License Reviews" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();
    expect(screen.getByText("jane.advisor@example.com")).toBeInTheDocument();
    expect(screen.getByText("CA • CA-LIC-9001")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Processed License Decisions" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Existing Advisor")).toBeInTheDocument();
  });

  it("approves a pending license and removes pending actions", async () => {
    vi.mocked(getProcessedLicenses)
      .mockResolvedValueOnce([processedLicense])
      .mockResolvedValueOnce([
        processedLicense,
        {
          ...processedLicense,
          license_id: pendingLicense.id,
          user_id: pendingLicense.user_id,
          user_name: pendingLicense.user_name,
          user_email: pendingLicense.user_email,
          state: pendingLicense.state,
          license_number: pendingLicense.license_number,
          license_type: pendingLicense.license_type,
          decision_status: "verified",
          decision_at: "2026-02-10T16:00:00Z",
          submission_type: "first_time",
          review_cycle: 1,
          rejection_reason: null,
          created_at: pendingLicense.created_at,
        },
      ]);

    render(<LicenseApproval />);

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(approveLicense).toHaveBeenCalledWith(101);
    });

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Approve" }),
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByText("License approved for Jane Advisor."),
    ).toBeInTheDocument();
    expect(getProcessedLicenses).toHaveBeenCalledTimes(2);
  });

  it("requires rejection reason and submits reject action", async () => {
    vi.mocked(getProcessedLicenses)
      .mockResolvedValueOnce([processedLicense])
      .mockResolvedValueOnce([
        processedLicense,
        {
          ...processedLicense,
          license_id: pendingLicense.id,
          user_id: pendingLicense.user_id,
          user_name: pendingLicense.user_name,
          user_email: pendingLicense.user_email,
          state: pendingLicense.state,
          license_number: pendingLicense.license_number,
          license_type: pendingLicense.license_type,
          decision_status: "rejected",
          decision_at: "2026-02-10T16:00:00Z",
          submission_type: "first_time",
          review_cycle: 1,
          rejection_reason: "Document unreadable",
          created_at: pendingLicense.created_at,
        },
      ]);

    render(<LicenseApproval />);

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    fireEvent.click(screen.getByRole("button", { name: "Confirm Reject" }));

    expect(
      screen.getByText("Rejection reason is required."),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Rejection reason"), {
      target: { value: "Document unreadable" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Reject" }));

    await waitFor(() => {
      expect(rejectLicense).toHaveBeenCalledWith(101, "Document unreadable");
    });

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: "Reject" }),
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByText("License rejected for Jane Advisor."),
    ).toBeInTheDocument();
  });

  it("shows action error and keeps row when approval fails", async () => {
    vi.mocked(approveLicense).mockRejectedValueOnce(
      new Error("Service unavailable"),
    );

    render(<LicenseApproval />);

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
    expect(screen.getByText("Jane Advisor")).toBeInTheDocument();
  });

  it("downloads the license document for review", async () => {
    render(<LicenseApproval />);

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Download Doc" })[0]);

    await waitFor(() => {
      expect(downloadLicenseDocument).toHaveBeenCalledWith(101);
    });

    expect(
      await screen.findByText("License document downloaded for Jane Advisor."),
    ).toBeInTheDocument();
  });

  it("opens inline document preview modal", async () => {
    render(<LicenseApproval />);

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "View Doc" })[0]);

    await waitFor(() => {
      expect(previewLicenseDocument).toHaveBeenCalledWith(101);
    });

    expect(
      await screen.findByRole("dialog", { name: "License document preview" }),
    ).toBeInTheDocument();
    expect(screen.getByTitle("License PDF preview")).toBeInTheDocument();
  });

  it("filters processed rows by advisor id", async () => {
    render(<LicenseApproval />);

    await screen.findByText("Existing Advisor");

    fireEvent.change(screen.getByLabelText("Filter by advisor"), {
      target: { value: "45" },
    });

    await waitFor(() => {
      expect(getProcessedLicenses).toHaveBeenLastCalledWith({
        advisorId: 45,
        advisorQuery: undefined,
      });
    });
  });

  it("paginates processed decisions with 10 rows per page", async () => {
    const processedRows = Array.from({ length: 12 }, (_, offset) =>
      buildProcessedDecision(offset + 1),
    );
    vi.mocked(getProcessedLicenses).mockResolvedValueOnce(processedRows);

    render(<LicenseApproval />);

    expect(await screen.findByText("Processed Advisor 1")).toBeInTheDocument();
    expect(screen.getByText("Processed Advisor 10")).toBeInTheDocument();
    expect(screen.queryByText("Processed Advisor 11")).not.toBeInTheDocument();
    expect(screen.queryByText("Processed Advisor 12")).not.toBeInTheDocument();
    expect(
      screen.getByText("Page 1 of 2 • 12 total processed licenses"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await screen.findByText("Processed Advisor 11");
    expect(screen.getByText("Processed Advisor 12")).toBeInTheDocument();
    expect(screen.queryByText("Processed Advisor 1")).not.toBeInTheDocument();
    expect(
      screen.getByText("Page 2 of 2 • 12 total processed licenses"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    await screen.findByText("Processed Advisor 1");
    expect(screen.queryByText("Processed Advisor 11")).not.toBeInTheDocument();
  });
});
