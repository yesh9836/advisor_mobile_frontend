import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMyLicenses, resubmitLicense } from "@/api/licenses";
import { LICENSE_DOCUMENT_ACCEPT } from "@/components/license/documentUpload";
import LicenseList from "@/components/license/LicenseList";
import type { License } from "@/types/license";

vi.mock("@/api/licenses", () => ({
  getMyLicenses: vi.fn(),
  resubmitLicense: vi.fn(),
}));

const rejectedLicense: License = {
  id: 22,
  user_id: 9,
  state: "AL",
  license_number: "DEMO-26-AL-001",
  license_type: "Series 65",
  has_document: true,
  verification_status: "rejected",
  verified_at: null,
  verified_by: null,
  rejection_reason: "Document is blurry",
  created_at: "2026-02-10T15:42:00Z",
};

describe("LicenseList", () => {
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getMyLicenses).mockResolvedValue([rejectedLicense]);
  });

  it("validates replacement document before resubmitting", async () => {
    render(<LicenseList />);

    expect(await screen.findByText("AL • DEMO-26-AL-001")).toBeInTheDocument();
    expect(screen.getByText("Rejection reason: Document is blurry")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resubmit" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm Resubmit" }));

    expect(
      screen.getByText("Please upload a replacement document."),
    ).toBeInTheDocument();
    expect(resubmitLicense).not.toHaveBeenCalled();
  });

  it("blocks unsupported replacement formats before calling the API", async () => {
    render(<LicenseList />);

    expect(await screen.findByText("AL • DEMO-26-AL-001")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resubmit" }));

    const fileInput = screen.getByLabelText("Upload replacement document (PDF, JPG, JPEG, or PNG)");
    expect(fileInput).toHaveAttribute("accept", LICENSE_DOCUMENT_ACCEPT);

    const file = new File(["animated"], "replacement.gif", {
      type: "image/gif",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Resubmit" }));

    expect(
      await screen.findByText("Document must be a PDF, JPG, JPEG, or PNG file."),
    ).toBeInTheDocument();
    expect(resubmitLicense).not.toHaveBeenCalled();
  });

  it("resubmits rejected license and updates row status", async () => {
    vi.mocked(resubmitLicense).mockResolvedValue({
      ...rejectedLicense,
      verification_status: "pending",
      rejection_reason: null,
      has_document: true,
    });

    render(<LicenseList />);

    expect(await screen.findByText("AL • DEMO-26-AL-001")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Resubmit" }));

    const fileInput = screen.getByLabelText(
      "Upload replacement document (PDF, JPG, JPEG, or PNG)",
    );
    const file = new File(["%PDF-1.4 retry"], "replacement.pdf", {
      type: "application/pdf",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    fireEvent.click(screen.getByRole("button", { name: "Confirm Resubmit" }));

    await waitFor(() => {
      expect(resubmitLicense).toHaveBeenCalledTimes(1);
    });

    const [licenseId, formData] = vi.mocked(resubmitLicense).mock.calls[0];
    expect(licenseId).toBe(22);
    expect(formData).toBeInstanceOf(FormData);
    expect((formData as FormData).get("document")).toBeInstanceOf(File);

    expect(
      await screen.findByText(
        "License AL • DEMO-26-AL-001 resubmitted successfully.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(
      screen.queryByText("Rejection reason: Document is blurry"),
    ).not.toBeInTheDocument();
  });

  it("ignores stale license loads after a refresh-triggered reload", async () => {
    const firstLoad = deferred<License[]>();
    const freshLicense: License = {
      ...rejectedLicense,
      id: 30,
      state: "CA",
      license_number: "FRESH-CA-30",
    };
    const staleLicense: License = {
      ...rejectedLicense,
      id: 31,
      state: "TX",
      license_number: "STALE-TX-31",
    };

    vi.mocked(getMyLicenses)
      .mockImplementationOnce(() => firstLoad.promise)
      .mockResolvedValueOnce([freshLicense]);

    const { rerender } = render(<LicenseList refreshKey={0} />);

    rerender(<LicenseList refreshKey={1} />);

    expect(await screen.findByText("CA • FRESH-CA-30")).toBeInTheDocument();

    firstLoad.resolve([staleLicense]);

    await waitFor(() => {
      expect(screen.queryByText("TX • STALE-TX-31")).not.toBeInTheDocument();
    });
    expect(screen.getByText("CA • FRESH-CA-30")).toBeInTheDocument();
  });
});
