import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMyGoal, saveMyGoal } from "@/api/goals";
import { createCheckout, getPackages } from "@/api/purchases";
import GoalsPage from "@/pages/advisor/GoalsPage";

vi.mock("@/api/goals", () => ({
  getMyGoal: vi.fn(),
  saveMyGoal: vi.fn(),
}));

vi.mock("@/api/purchases", () => ({
  createCheckout: vi.fn(),
  getPackages: vi.fn(),
}));

const getMyGoalMock = vi.mocked(getMyGoal);
const saveMyGoalMock = vi.mocked(saveMyGoal);
const createCheckoutMock = vi.mocked(createCheckout);
const getPackagesMock = vi.mocked(getPackages);

const buildGoalResponse = () => ({
  goal: {
    id: 1,
    user_id: 2,
    target_year: new Date().getFullYear(),
    annual_income_goal_cents: 25_000_000,
    average_commission_cents: 350_000,
    earned_ytd_cents: 7_800_000,
    appointment_to_deal_rate_bps: 1_200,
    lead_to_appointment_rate_bps: 2_500,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
  },
  derived: {
    deals_needed: 72,
    appointments_needed: 600,
    leads_needed: 2400,
    closed_deals_ytd: 2,
    income_progress_percent: 31,
    deals_remaining: 50,
    appointments_remaining: 410,
    leads_remaining: 1639,
    recommended_monthly_leads: 235,
    pacing: {
      remaining_months: 7,
      recommended_monthly_leads: 235,
      status: "active",
      message: "Buy about 235 leads/month for the rest of the year.",
    },
  },
  packages: [
    {
      package_id: 1,
      name: "Starter",
      price_cents: 7_500,
      currency: "USD",
      credits_per_package: 50,
      packages_needed: 34,
      total_cost_cents: 255_000,
      estimated_cost_per_lead_cents: 150,
      state_limit: 1,
      features: null,
      overage_leads: 14,
      recommended: false,
    },
    {
      package_id: 2,
      name: "Growth",
      price_cents: 20_000,
      currency: "USD",
      credits_per_package: 200,
      packages_needed: 9,
      total_cost_cents: 180_000,
      estimated_cost_per_lead_cents: 100,
      state_limit: null,
      features: null,
      overage_leads: 64,
      recommended: true,
    },
  ],
});

const buildIncomeGoalMetResponse = () => {
  const response = buildGoalResponse();
  return {
    ...response,
    goal: {
      ...response.goal,
      earned_ytd_cents: response.goal.annual_income_goal_cents,
    },
    derived: {
      ...response.derived,
      income_progress_percent: 100,
      deals_remaining: 0,
      appointments_remaining: 0,
      leads_remaining: 0,
      recommended_monthly_leads: 0,
      pacing: {
        remaining_months: 7,
        recommended_monthly_leads: 0,
        status: "goal_met",
        message: "Annual income goal met.",
      },
    },
    packages: [],
  };
};

const renderPage = () => {
  render(<GoalsPage />);
};

const buildPackageCatalog = () => [
  {
    id: 11,
    name: "Starter Live",
    price_cents: 3_999,
    currency: "USD",
    state_limit: 1,
    daily_download_limit: 2,
    credits_total: 50,
    features: ["2 leads"],
    stripe_price_id: "price_starter_live",
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 22,
    name: "Growth Live",
    price_cents: 3_999,
    currency: "USD",
    state_limit: null,
    daily_download_limit: 4,
    credits_total: 200,
    features: ["200 leads"],
    stripe_price_id: "price_growth_live",
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("Advisor Goals page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMyGoalMock.mockResolvedValue(buildGoalResponse());
    saveMyGoalMock.mockResolvedValue(buildGoalResponse());
    getPackagesMock.mockResolvedValue(buildPackageCatalog());
    createCheckoutMock.mockResolvedValue({
      session_id: "cs_test",
      url: "https://checkout.example.test",
    });
  });

  it("renders the saved goal, derived values, high-level closed deals, and live packages", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Goals" })).toBeInTheDocument();
    expect(screen.getAllByText("$250,000").length).toBeGreaterThan(0);
    expect(screen.getByText("$78,000")).toBeInTheDocument();
    expect(screen.getByText("31% there")).toBeInTheDocument();
    expect(screen.getByText("Closed YTD")).toBeInTheDocument();
    expect(screen.queryByText("Actual closed deals YTD")).not.toBeInTheDocument();
    expect(screen.queryByText("Estimated from manual earned YTD")).not.toBeInTheDocument();
    expect(screen.getByText("Growth Live")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getAllByText("$39.99").length).toBeGreaterThan(0);
    expect(screen.getAllByText("/package").length).toBeGreaterThan(0);
    expect(screen.queryByText("/lead")).not.toBeInTheDocument();
    expect(
      screen.getByText((text) =>
        text.includes("9 packages x $39.99 = $359.91"),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("1,800 leads total (200 per package)")).toBeInTheDocument();
    expect(
      screen.getByText((text) =>
        text.includes("Estimated full-plan spend: $359.91"),
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText((text) =>
        text.includes("Buy about 235 leads/month") &&
        text.includes("2 Growth Live packages/month"),
      ),
    ).toBeInTheDocument();
  });

  it("keeps earned YTD manual and recalculates income progress and lead volume", async () => {
    renderPage();

    const earnedInput = await screen.findByLabelText("Earned year-to-date");
    fireEvent.change(earnedInput, { target: { value: "87500" } });

    await waitFor(() => {
      expect(
        screen.getByText((text) => text.includes("1,548 additional leads")),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("35% there")).toBeInTheDocument();
  });

  it("updates recommended lead volume when earned YTD changes in the form", async () => {
    renderPage();

    fireEvent.change(await screen.findByLabelText("Annual income goal"), {
      target: { value: "10000" },
    });
    fireEvent.change(screen.getByLabelText("Avg commission per deal"), {
      target: { value: "500" },
    });
    fireEvent.change(screen.getByLabelText("Earned year-to-date"), {
      target: { value: "400" },
    });
    fireEvent.change(screen.getByLabelText("Closing rate (appt to deal)"), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText("Lead to appointment rate"), {
      target: { value: "5" },
    });

    await waitFor(() => {
      expect(
        screen.getByText((text) => text.includes("12,800 additional leads")),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Earned year-to-date"), {
      target: { value: "1000" },
    });

    await waitFor(() => {
      expect(
        screen.getByText((text) => text.includes("12,000 additional leads")),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText((text) => text.includes("12,800 additional leads")),
    ).not.toBeInTheDocument();
  });

  it("updates lead volume and package spend across partial commission progress", async () => {
    renderPage();

    fireEvent.change(await screen.findByLabelText("Annual income goal"), {
      target: { value: "10000" },
    });
    fireEvent.change(screen.getByLabelText("Avg commission per deal"), {
      target: { value: "3500" },
    });
    fireEvent.change(screen.getByLabelText("Closing rate (appt to deal)"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Lead to appointment rate"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Earned year-to-date"), {
      target: { value: "3000" },
    });

    await waitFor(() => {
      expect(screen.getByText((text) => text.includes("800 additional leads"))).toBeInTheDocument();
      expect(
        screen.getByText((text) => text.includes("4 packages x $39.99 = $159.96")),
      ).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText("Earned year-to-date"), {
      target: { value: "9000" },
    });

    await waitFor(() => {
      expect(screen.getByText((text) => text.includes("115 additional leads"))).toBeInTheDocument();
      expect(
        screen.getByText((text) => text.includes("1 package x $39.99 = $39.99")),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByText((text) => text.includes("800 additional leads")),
    ).not.toBeInTheDocument();
  });

  it("shows goal met instead of package recommendations when earned YTD reaches the income goal", async () => {
    getMyGoalMock.mockResolvedValueOnce(buildIncomeGoalMetResponse());

    renderPage();

    expect(await screen.findByText("100% there")).toBeInTheDocument();
    expect(screen.getAllByText("Annual income goal met.").length).toBeGreaterThan(0);
    expect(
      screen.getByText("Annual income goal met. No additional lead packages are recommended."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Growth Live")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Buy 1 Package" })).not.toBeInTheDocument();
    expect(screen.queryByText("No current lead packages are available.")).not.toBeInTheDocument();
  });

  it("starts checkout for the exact listed package ID", async () => {
    renderPage();

    const growthCard = await screen.findByText("Growth Live");
    const card = growthCard.closest("article");
    expect(card).not.toBeNull();
    fireEvent.click(
      screen.getAllByRole("button", { name: "Buy 1 Package" }).find((button) =>
        card?.contains(button),
      ) as HTMLButtonElement,
    );

    await waitFor(() => {
      expect(createCheckoutMock).toHaveBeenCalledWith(22);
    });
  });

  it("saves edited values explicitly and shows success", async () => {
    renderPage();

    fireEvent.change(await screen.findByLabelText("Annual income goal"), {
      target: { value: "300000" },
    });
    fireEvent.change(screen.getByLabelText("Closing rate (appt to deal)"), {
      target: { value: "15" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Goal" }));

    await waitFor(() => {
      expect(saveMyGoalMock).toHaveBeenCalledWith(
        expect.objectContaining({
          annual_income_goal_cents: 30_000_000,
          appointment_to_deal_rate_bps: 1_500,
        }),
      );
    });
    expect(await screen.findByText("Goal saved.")).toBeInTheDocument();
  });

  it("shows validation errors and save failures", async () => {
    saveMyGoalMock.mockRejectedValueOnce(new Error("Save failed"));
    renderPage();

    fireEvent.change(await screen.findByLabelText("Avg commission per deal"), {
      target: { value: "0" },
    });

    expect(screen.getByText("Average commission must be greater than zero.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Goal" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Avg commission per deal"), {
      target: { value: "3500" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Goal" }));

    expect(await screen.findByText("Save failed")).toBeInTheDocument();
  });
});
