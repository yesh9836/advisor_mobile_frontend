import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Header from "@/components/layout/Header";

const logoutMock = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("Layout Header", () => {
  it("shows right-side user details and hides non-functional header controls", () => {
    mockUseAuth.mockReturnValue({
      user: {
        role: "advisor",
        name: "Alex Advisor",
        email: "alex@example.com",
      },
      logout: logoutMock,
    });

    render(<Header />);

    expect(screen.queryByRole("searchbox", { name: "Search" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Notifications" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Settings" })).not.toBeInTheDocument();
    expect(screen.queryByText("Advisor View")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin View")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Spectaculeads logo" })).toBeInTheDocument();
    expect(screen.getByText("Alex Advisor")).toBeInTheDocument();
    expect(screen.getByText("alex@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Logout" })).toBeInTheDocument();
  });
});
