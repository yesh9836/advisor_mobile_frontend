import { beforeEach, describe, expect, it, vi } from "vitest";

import apiClient from "@/api/client";
import { getMyGoal, saveMyGoal } from "@/api/goals";

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    put: vi.fn(),
  },
}));

type MockFn = ReturnType<typeof vi.fn>;

const mockedApiClient = apiClient as unknown as {
  get: MockFn;
  put: MockFn;
};

const goalResponse = {
  goal: {
    id: 1,
    user_id: 2,
    target_year: 2026,
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
};

describe("goals API contract", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.put.mockReset();
  });

  it("gets the current goal with optional target year", async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: goalResponse });

    await expect(getMyGoal(2026)).resolves.toEqual(goalResponse);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/goals/me", {
      params: { target_year: 2026 },
      signal: undefined,
    });
  });

  it("saves the goal and rejects invalid response contracts", async () => {
    mockedApiClient.put.mockResolvedValueOnce({ data: goalResponse });

    await expect(saveMyGoal(goalResponse.goal)).resolves.toEqual(goalResponse);

    mockedApiClient.put.mockResolvedValueOnce({
      data: { ...goalResponse, derived: { leads_needed: "bad" } },
    });

    await expect(saveMyGoal(goalResponse.goal)).rejects.toThrow(
      "Unexpected response format from /goals/me",
    );
  });
});
