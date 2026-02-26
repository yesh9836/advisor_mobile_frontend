import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FirstPurchaseOfferPage from "@/pages/admin/FirstPurchaseOfferPage";

const getFirstPurchaseOfferConfig = vi.fn();
const updateFirstPurchaseOfferConfig = vi.fn();
const getPackages = vi.fn();

vi.mock("@/api/admin", () => ({
  getFirstPurchaseOfferConfig: (...args: unknown[]) => getFirstPurchaseOfferConfig(...args),
  updateFirstPurchaseOfferConfig: (...args: unknown[]) => updateFirstPurchaseOfferConfig(...args),
}));

vi.mock("@/api/purchases", () => ({
  getPackages: (...args: unknown[]) => getPackages(...args),
}));

describe("FirstPurchaseOfferPage USD-only currency", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    getPackages.mockResolvedValue([
      {
        id: 101,
        name: "Starter",
        price_cents: 12000,
        currency: "USD",
        state_limit: 1,
        daily_download_limit: 10,
        features: ["starter"],
        stripe_price_id: "price_starter_offer",
        created_at: "2026-02-26T12:00:00Z",
      },
    ]);

    getFirstPurchaseOfferConfig.mockResolvedValue({
      id: 1,
      is_enabled: false,
      trigger_package_id: null,
      trigger_package_name: null,
      offer_package_id: null,
      offer_package_name: null,
      offer_price_cents: null,
      offer_currency: "USD",
      offer_credits_total: null,
      headline: null,
      message: null,
      cta_label: null,
      starts_at: null,
      ends_at: null,
      updated_at: null,
      updated_by: null,
      inventory_ready: null,
      inventory_available_count: null,
      inventory_required_count: null,
      inventory_gate_code: null,
      inventory_gate_message: null,
    });

    updateFirstPurchaseOfferConfig.mockResolvedValue({
      id: 1,
      is_enabled: true,
      trigger_package_id: 101,
      trigger_package_name: "Starter",
      offer_package_id: 202,
      offer_package_name: "First Purchase Add-on",
      offer_price_cents: 7500,
      offer_currency: "USD",
      offer_credits_total: 5,
      headline: null,
      message: null,
      cta_label: null,
      starts_at: null,
      ends_at: null,
      updated_at: "2026-02-26T12:05:00Z",
      updated_by: 7,
      inventory_ready: false,
      inventory_available_count: 0,
      inventory_required_count: 5,
      inventory_gate_code: "INVENTORY_UNAVAILABLE",
      inventory_gate_message: "Global add-on inventory is currently below the required threshold",
    });
  });

  it("removes editable currency input and always submits USD", async () => {
    render(
      <MemoryRouter>
        <FirstPurchaseOfferPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Offer Rules")).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Currency" })).not.toBeInTheDocument();
    expect(screen.getByText("USD")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Enable Offer" }));
    fireEvent.change(screen.getByLabelText("Purchased Package (Trigger)"), {
      target: { value: "101" },
    });
    fireEvent.change(screen.getByLabelText("Add-on Leads"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Add-on Price (Dollars)"), {
      target: { value: "75.00" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save Offer" }));

    await waitFor(() => {
      expect(updateFirstPurchaseOfferConfig).toHaveBeenCalledTimes(1);
    });
    expect(updateFirstPurchaseOfferConfig).toHaveBeenCalledWith(
      expect.objectContaining({
        offer_currency: "USD",
      }),
    );
    expect(await screen.findByTestId("offer-inventory-status")).toHaveTextContent(
      "Code: INVENTORY_UNAVAILABLE",
    );
  });
});
