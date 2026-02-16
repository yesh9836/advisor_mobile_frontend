import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Sidebar from "@/components/layout/Sidebar";

const mockUseAuth = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const renderSidebar = () => {
  render(
    <MemoryRouter>
      <Sidebar isOpen={false} onClose={vi.fn()} />
    </MemoryRouter>,
  );
};

describe("Sidebar role-based navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows advisor navigation for advisor users", () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
    });

    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Buy Leads")).toBeInTheDocument();
    expect(screen.getByText("Lead Inbox")).toBeInTheDocument();
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Billing")).toBeInTheDocument();
    expect(screen.queryByText("Lead Inventory")).not.toBeInTheDocument();
    expect(screen.queryByText("Orders")).not.toBeInTheDocument();
    expect(screen.queryByText("Imports")).not.toBeInTheDocument();
    expect(screen.getByText("NEXT STEP")).toBeInTheDocument();
  });

  it("shows admin-only navigation for admin users", () => {
    mockUseAuth.mockReturnValue({
      user: { role: "admin" },
    });

    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Lead Inventory")).toBeInTheDocument();
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Orders")).toBeInTheDocument();
    expect(screen.getByText("Imports")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("License Reviews")).toBeInTheDocument();
    expect(screen.queryByText("Buy Leads")).not.toBeInTheDocument();
    expect(screen.queryByText("Lead Inbox")).not.toBeInTheDocument();
    expect(screen.queryByText("Billing")).not.toBeInTheDocument();
    expect(screen.queryByText("Profile")).not.toBeInTheDocument();
    expect(screen.queryByText("NEXT STEP")).not.toBeInTheDocument();
  });
});
