import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMyGoal, saveMyGoal } from "@/api/goals";
import { createCheckout } from "@/api/purchases";
import GoalsPage from "@/pages/advisor/GoalsPage";

vi.mock("@/api/goals", () => ({
  getMyGoal: vi.fn(),
  saveMyGoal: vi.fn(),
}));

vi.mock("@/api/purchases", () => ({
  createCheckout: vi.fn(),
}));

const getMyGoalMock = vi.mocked(getMyGoal);
const saveMyGoalMock = vi.mocked(saveMyGoal);
const createCheckoutMock = vi.mocked(createCheckout);

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
    estimated_deals_from_earned_ytd: 22,
    income_progress_percent: 31,
    deals_remaining: 50,
    appointments_remaining: 417,
    leads_remaining: 1667,
    recommended_monthly_leads: 239,
    pacing: {
      remaining_months: 7,
      recommended_monthly_leads: 239,
      status: "active",
      message: "Buy about 239 leads/month for the rest of the year.",
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
      recommended: true,
    },
  ],
});

const renderPage = () => {
  render(<GoalsPage />);
};

describe("Advisor Goals page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMyGoalMock.mockResolvedValue(buildGoalResponse());
    saveMyGoalMock.mockResolvedValue(buildGoalResponse());
    createCheckoutMock.mockResolvedValue({
      session_id: "cs_test",
      url: "https://checkout.example.test",
    });
  });

  it("renders the saved goal, derived values, actual closed deals, and live packages", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { name: "Goals" })).toBeInTheDocument();
    expect(screen.getAllByText("$250,000").length).toBeGreaterThan(0);
    expect(screen.getByText("$78,000")).toBeInTheDocument();
    expect(screen.getByText("31% there")).toBeInTheDocument();
    expect(screen.getByText("Actual closed deals YTD")).toBeInTheDocument();
    expect(screen.getByText("Growth")).toBeInTheDocument();
    expect(screen.getByText("Recommended")).toBeInTheDocument();
    expect(screen.getByText("Buy about 239 leads/month for the rest of the year.")).toBeInTheDocument();
  });

  it("recalculates visible values while editing before save", async () => {
    renderPage();

    const earnedInput = await screen.findByLabelText("Earned year-to-date");
    fireEvent.change(earnedInput, { target: { value: "87500" } });

    await waitFor(() => {
      expect(
        screen.getByText((text) => text.includes("1,567 more leads")),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("35% there")).toBeInTheDocument();
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
