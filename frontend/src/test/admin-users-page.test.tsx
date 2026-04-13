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
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  };

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
    expect(getUsers).toHaveBeenCalledWith(
      1,
      20,
      {},
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
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
      }, expect.objectContaining({
        signal: expect.any(AbortSignal),
      }));
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
      expect(getUsers).toHaveBeenLastCalledWith(
        1,
        10,
        {},
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });
  });

  it("ignores stale user responses after a newer page-size request", async () => {
    const firstResponse = deferred<{
      items: Array<Record<string, unknown>>;
      total: number;
      page: number;
      size: number;
    }>();

    getUsers
      .mockImplementationOnce(() => firstResponse.promise)
      .mockResolvedValueOnce({
        items: [
          {
            id: 22,
            name: "Alex Admin",
            email: "alex@example.com",
            role: "admin",
            is_active: true,
            created_at: "2026-02-11T12:00:00Z",
            license_count: 0,
            current_credits: 0,
            total_purchases: 0,
          },
        ],
        total: 1,
        page: 1,
        size: 20,
      });

    render(
      <MemoryRouter>
        <UsersPage />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Rows per page"), {
      target: { value: "10" },
    });

    expect(await screen.findByText("Alex Admin")).toBeInTheDocument();

    firstResponse.resolve({
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
      size: 10,
    });

    await waitFor(() => {
      expect(screen.queryByText("Jane Advisor")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Alex Admin")).toBeInTheDocument();
  });
});
