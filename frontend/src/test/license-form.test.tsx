import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LicenseForm from "@/components/license/LicenseForm";

vi.mock("@/api/licenses", () => ({
  submitLicense: vi.fn(),
}));

describe("LicenseForm", () => {
  it("uses generic license type placeholder text", () => {
    render(<LicenseForm />);

    expect(screen.getByPlaceholderText("Enter license type")).toBeInTheDocument();
    expect(
      screen.queryByPlaceholderText("Example: Series 65, Insurance Producer"),
    ).not.toBeInTheDocument();
  });
});
