import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { submitLicense } from "@/api/licenses";
import { LICENSE_DOCUMENT_ACCEPT } from "@/components/license/documentUpload";
import LicenseForm from "@/components/license/LicenseForm";

vi.mock("@/api/licenses", () => ({
  submitLicense: vi.fn(),
}));

describe("LicenseForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses generic license type placeholder text", () => {
    render(<LicenseForm />);

    expect(screen.getByPlaceholderText("Enter license type")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Example: Series 65, Insurance Producer"),
    ).not.toBeInTheDocument();
  });

  it("limits the file chooser to backend-supported document types", () => {
    render(<LicenseForm />);

    expect(screen.getByLabelText("Document upload (PDF, JPG, JPEG, or PNG)")).toHaveAttribute(
      "accept",
      LICENSE_DOCUMENT_ACCEPT,
    );
  });

  it("blocks unsupported image formats before submitting", async () => {
    const { container } = render(<LicenseForm />);

    fireEvent.change(screen.getByLabelText("State"), { target: { value: "CA" } });
    fireEvent.change(screen.getByLabelText("License number"), {
      target: { value: "CA-LIC-4001" },
    });

    const fileInput = screen.getByLabelText("Document upload (PDF, JPG, JPEG, or PNG)");
    const file = new File(["webp-license"], "license.webp", {
      type: "image/webp",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    const form = container.querySelector("form");
    if (!form) {
      throw new Error("License form was not rendered");
    }
    fireEvent.submit(form);

    expect(
      await screen.findByText("Document must be a PDF, JPG, JPEG, or PNG file."),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(submitLicense).not.toHaveBeenCalled();
    });
  });
});
