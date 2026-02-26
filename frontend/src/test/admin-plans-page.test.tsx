import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PlansPage from "@/pages/admin/PlansPage";

const getAdminPlans = vi.fn();
const createAdminPlan = vi.fn();
const updateAdminPlan = vi.fn();
const archiveAdminPlan = vi.fn();
const unarchiveAdminPlan = vi.fn();

vi.mock("@/api/admin", () => ({
  getAdminPlans: (...args: unknown[]) => getAdminPlans(...args),
  createAdminPlan: (...args: unknown[]) => createAdminPlan(...args),
  updateAdminPlan: (...args: unknown[]) => updateAdminPlan(...args),
  archiveAdminPlan: (...args: unknown[]) => archiveAdminPlan(...args),
  unarchiveAdminPlan: (...args: unknown[]) => unarchiveAdminPlan(...args),
}));

const buildPlan = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 7,
  name: "Growth 25",
  price_cents: 25000,
  currency: "USD",
  stripe_product_id: "prod_growth_25",
  stripe_price_id: "price_growth_25",
  state_limit: 3,
  credits_total: 25,
  catalog_visible: true,
  is_archived: false,
  archived_at: null,
  effective_from: null,
  effective_to: null,
  created_at: "2026-02-26T12:00:00Z",
  updated_at: "2026-02-26T12:10:00Z",
  updated_by: 1,
  has_purchases: false,
  ...overrides,
});

describe("PlansPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "confirm").mockReturnValue(true);

    getAdminPlans.mockResolvedValue({
      items: [buildPlan()],
      total: 1,
      page: 1,
      size: 100,
    });
    createAdminPlan.mockResolvedValue(buildPlan({ id: 8, name: "Growth 40" }));
    updateAdminPlan.mockResolvedValue(buildPlan({ name: "Growth 30", credits_total: 30 }));
    archiveAdminPlan.mockResolvedValue(buildPlan({ is_archived: true, archived_at: "2026-02-27T10:00:00Z" }));
    unarchiveAdminPlan.mockResolvedValue(buildPlan({ is_archived: false, archived_at: null }));
  });

  it("loads and renders existing plans", async () => {
    render(
      <MemoryRouter>
        <PlansPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Growth 25")).toBeInTheDocument();
    expect(getAdminPlans).toHaveBeenCalledWith(1, 100, {
      archived: "all",
      search: "",
    });
  });

  it("creates a new plan from form input", async () => {
    render(
      <MemoryRouter>
        <PlansPage />
      </MemoryRouter>,
    );

    await screen.findByText("Growth 25");

    fireEvent.change(screen.getByLabelText("Plan Name"), {
      target: { value: "Growth 40" },
    });
    fireEvent.change(screen.getByLabelText("Price (USD)"), {
      target: { value: "400.00" },
    });
    fireEvent.change(screen.getByLabelText("Credits"), {
      target: { value: "40" },
    });
    fireEvent.change(screen.getByLabelText("State Limit (optional)"), {
      target: { value: "4" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Create Plan" }));

    await waitFor(() => {
      expect(createAdminPlan).toHaveBeenCalledTimes(1);
    });

    expect(createAdminPlan).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "Growth 40",
        price_cents: 40000,
        credits_total: 40,
        state_limit: 4,
        catalog_visible: true,
      }),
    );
    expect(createAdminPlan.mock.calls[0][0].request_id).toMatch(/^plan_create_/);
  });

  it("edits and archives an existing plan", async () => {
    render(
      <MemoryRouter>
        <PlansPage />
      </MemoryRouter>,
    );

    await screen.findByText("Growth 25");

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Price (USD)"), {
      target: { value: "300.00" },
    });
    fireEvent.change(screen.getByLabelText("Credits"), {
      target: { value: "30" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Plan" }));

    await waitFor(() => {
      expect(updateAdminPlan).toHaveBeenCalledTimes(1);
    });
    expect(updateAdminPlan).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        price_cents: 30000,
        credits_total: 30,
      }),
    );
    expect(updateAdminPlan.mock.calls[0][1].request_id).toMatch(/^plan_update_/);

    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => {
      expect(archiveAdminPlan).toHaveBeenCalledWith(7);
    });
  });

  it("unarchives archived plans", async () => {
    getAdminPlans.mockResolvedValueOnce({
      items: [buildPlan({ is_archived: true, archived_at: "2026-02-27T10:00:00Z" })],
      total: 1,
      page: 1,
      size: 100,
    });

    render(
      <MemoryRouter>
        <PlansPage />
      </MemoryRouter>,
    );

    await screen.findByText("Growth 25");
    fireEvent.click(screen.getByRole("button", { name: "Unarchive" }));

    await waitFor(() => {
      expect(unarchiveAdminPlan).toHaveBeenCalledWith(7);
    });
  });
});
