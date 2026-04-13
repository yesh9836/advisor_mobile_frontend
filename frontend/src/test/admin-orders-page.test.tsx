import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrdersPage from "@/pages/admin/OrdersPage";
import type { AdminOrderListItem } from "@/types/admin";

const getOrders = vi.fn();
const downloadOrdersExport = vi.fn();

vi.mock("@/api/admin", () => ({
  getOrders: (...args: unknown[]) => getOrders(...args),
  downloadOrdersExport: (...args: unknown[]) => downloadOrdersExport(...args),
}));

const buildOrder = (index: number): AdminOrderListItem => ({
  id: index,
  order_reference: `order-${index}`,
  advisor_name: `Advisor ${index}`,
  advisor_email: `advisor${index}@example.com`,
  package_name: "Starter",
  quantity: 1,
  remaining_credits: 10,
  status: "completed",
  created_at: "2026-02-10T12:00:00Z",
  amount_cents: 9900,
  currency: "USD",
});

describe("OrdersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getOrders.mockResolvedValue({
      items: [buildOrder(1)],
      total: 1,
      page: 1,
      size: 10,
    });
    downloadOrdersExport.mockResolvedValue({
      blob: new Blob(["csv"], { type: "text/csv" }),
      filename: "orders.csv",
    });
  });

  it("loads orders with fixed page size 10", async () => {
    render(<OrdersPage />);

    expect(await screen.findByText("Advisor 1 • Starter (1)")).toBeInTheDocument();
    expect(getOrders).toHaveBeenCalledWith(
      1,
      10,
      undefined,
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    expect(screen.getByText("Page 1 of 1 • 1 total orders")).toBeInTheDocument();
  });

  it("paginates with previous and next buttons", async () => {
    getOrders
      .mockResolvedValueOnce({
        items: Array.from({ length: 10 }, (_, offset) => buildOrder(offset + 1)),
        total: 12,
        page: 1,
        size: 10,
      })
      .mockResolvedValueOnce({
        items: [buildOrder(11), buildOrder(12)],
        total: 12,
        page: 2,
        size: 10,
      })
      .mockResolvedValueOnce({
        items: Array.from({ length: 10 }, (_, offset) => buildOrder(offset + 1)),
        total: 12,
        page: 1,
        size: 10,
      });

    render(<OrdersPage />);

    expect(await screen.findByText("Advisor 1 • Starter (1)")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 2 • 12 total orders")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    await waitFor(() => {
      expect(getOrders).toHaveBeenLastCalledWith(
        2,
        10,
        undefined,
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });
    expect(await screen.findByText("Advisor 11 • Starter (1)")).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 2 • 12 total orders")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));

    await waitFor(() => {
      expect(getOrders).toHaveBeenLastCalledWith(
        1,
        10,
        undefined,
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });
    expect(await screen.findByText("Advisor 1 • Starter (1)")).toBeInTheDocument();
  });

});
