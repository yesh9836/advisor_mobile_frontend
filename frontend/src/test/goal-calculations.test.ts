import { describe, expect, it } from "vitest";

import {
  calculateGoalPreview,
  parseMoneyToCents,
  parsePercentToBasisPoints,
  recalculatePackageRecommendation,
} from "@/pages/advisor/goalCalculations";

describe("goal calculations", () => {
  it("matches the documented goal formulas and caps progress", () => {
    const derived = calculateGoalPreview(
      {
        target_year: new Date().getFullYear(),
        annual_income_goal_cents: 25_000_000,
        average_commission_cents: 350_000,
        earned_ytd_cents: 7_800_000,
        appointment_to_deal_rate_bps: 1_200,
        lead_to_appointment_rate_bps: 2_500,
      },
      3,
    );

    expect(derived.deals_needed).toBe(72);
    expect(derived.appointments_needed).toBe(600);
    expect(derived.leads_needed).toBe(2400);
    expect(derived.closed_deals_ytd).toBe(3);
    expect(derived.estimated_deals_from_earned_ytd).toBe(22);
    expect(derived.income_progress_percent).toBe(31);
    expect(derived.deals_remaining).toBe(50);
    expect(derived.appointments_remaining).toBe(417);
    expect(derived.leads_remaining).toBe(1667);

    const overGoal = calculateGoalPreview(
      { ...derivedPayload(), earned_ytd_cents: 30_000_000 },
      4,
    );
    expect(overGoal.income_progress_percent).toBe(100);
    expect(overGoal.leads_remaining).toBe(0);
  });

  it("parses currency and percent fields into storage units", () => {
    expect(parseMoneyToCents("250,000")).toBe(25_000_000);
    expect(parseMoneyToCents("3500.50")).toBe(350_050);
    expect(parseMoneyToCents("abc")).toBeNull();
    expect(parsePercentToBasisPoints("12")).toBe(1200);
    expect(parsePercentToBasisPoints("12.25")).toBe(1225);
    expect(parsePercentToBasisPoints("")).toBeNull();
  });

  it("recalculates package totals from live package metadata", () => {
    const recommendation = recalculatePackageRecommendation(
      {
        package_id: 7,
        name: "Growth",
        price_cents: 20_000,
        currency: "USD",
        credits_per_package: 200,
        packages_needed: 1,
        total_cost_cents: 20_000,
        estimated_cost_per_lead_cents: 100,
        state_limit: null,
        features: null,
        recommended: false,
      },
      450,
    );

    expect(recommendation.packages_needed).toBe(3);
    expect(recommendation.total_cost_cents).toBe(60_000);
    expect(recommendation.estimated_cost_per_lead_cents).toBe(100);
  });
});

const derivedPayload = () => ({
  target_year: new Date().getFullYear(),
  annual_income_goal_cents: 25_000_000,
  average_commission_cents: 350_000,
  earned_ytd_cents: 7_800_000,
  appointment_to_deal_rate_bps: 1_200,
  lead_to_appointment_rate_bps: 2_500,
});
