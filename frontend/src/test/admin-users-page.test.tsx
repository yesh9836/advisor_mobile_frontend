import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "@/pages/admin/UsersPage";

const getUsers = vi.fn();
const navigateMock = vi.fn();

vi.mock("@/api/admin", () => ({
  getUsers: (...args: unknown[]) => getUsers(...args),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );

  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getUsers.mockResolvedValue({
      items: [
        {
          id: 11,
          name: "Jane Advisor",
          email: "jane@example.com",
          role: "advisor",
          is_active: true,
          created_at: "2026-02-10T12:00:00Z",
          license_count: 2,
          current_credits: 14,
          total_purchases: 3,
        },
      ],
      total: 1,
      page: 1,
      size: 20,
    });
  });

  it("loads and renders user rows", async () => {
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Jane Advisor")).toBeInTheDocument();
    expect(screen.getByText("jane@example.com")).toBeInTheDocument();
    expect(getUsers).toHaveBeenCalledWith(1, 20, {});
  });

  it("applies filters and requests filtered results", async () => {
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    await screen.findByText("Jane Advisor");

    fireEvent.change(screen.getByLabelText("Search"), {
      target: { value: " jane " },
    });
    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "advisor" },
    });
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "active" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply Filters" }));

    await waitFor(() => {
      expect(getUsers).toHaveBeenLastCalledWith(1, 20, {
        search: "jane",
        role: "advisor",
        status: "active",
      });
    });
  });

  it("navigates to user details on row click", async () => {
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    const rowButton = await screen.findByRole("button", {
      name: "View details for Jane Advisor",
    });

    fireEvent.click(rowButton);
    expect(navigateMock).toHaveBeenCalledWith("/admin/users/11");
  });

  it("changes page size and reloads results", async () => {
    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    await screen.findByText("Jane Advisor");

    fireEvent.change(screen.getByLabelText("Rows per page"), {
      target: { value: "10" },
    });

    await waitFor(() => {
      expect(getUsers).toHaveBeenLastCalledWith(1, 10, {});
    });
  });
});
