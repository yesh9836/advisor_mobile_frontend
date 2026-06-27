import { describe, expect, it } from "vitest";

import {
  calculateGoalPreview,
  packageCatalogToGoalRecommendation,
  parseMoneyToCents,
  parsePercentToBasisPoints,
  rankPackageRecommendations,
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
    expect(derived.income_progress_percent).toBe(31);
    expect(derived.deals_remaining).toBe(50);
    expect(derived.appointments_remaining).toBe(410);
    expect(derived.leads_remaining).toBe(1639);

    const overGoal = calculateGoalPreview(
      { ...derivedPayload(), earned_ytd_cents: 30_000_000 },
      4,
    );
    expect(overGoal.income_progress_percent).toBe(100);
    expect(overGoal.deals_remaining).toBe(0);
    expect(overGoal.leads_remaining).toBe(0);
    expect(overGoal.pacing.status).toBe("goal_met");
    expect(overGoal.pacing.message).toBe("Annual income goal met.");
  });

  it("does not rank packages when no leads remain", () => {
    const ranked = rankPackageRecommendations(
      [
        recommendationFixture({
          package_id: 10,
          name: "Starter",
          price_cents: 100,
          credits_per_package: 100,
        }),
      ],
      0,
    );

    expect(ranked).toEqual([]);
  });

  it("updates remaining volume from manual earned YTD even when closed deals exist", () => {
    const payload = {
      target_year: new Date().getFullYear(),
      annual_income_goal_cents: 1_000_000,
      average_commission_cents: 50_000,
      earned_ytd_cents: 40_000,
      appointment_to_deal_rate_bps: 300,
      lead_to_appointment_rate_bps: 500,
    };

    const earned400 = calculateGoalPreview(payload, 2);
    const earned1000 = calculateGoalPreview(
      { ...payload, earned_ytd_cents: 100_000 },
      2,
    );

    expect(earned400.deals_remaining).toBe(20);
    expect(earned400.appointments_remaining).toBe(640);
    expect(earned400.leads_remaining).toBe(12800);
    expect(earned1000.deals_remaining).toBe(18);
    expect(earned1000.appointments_remaining).toBe(600);
    expect(earned1000.leads_remaining).toBe(12000);
  });

  it("changes lead volume within a single average-commission band", () => {
    const payload = {
      target_year: new Date().getFullYear(),
      annual_income_goal_cents: 1_000_000,
      average_commission_cents: 350_000,
      earned_ytd_cents: 300_000,
      appointment_to_deal_rate_bps: 500,
      lead_to_appointment_rate_bps: 500,
    };

    const earned3000 = calculateGoalPreview(payload, 0);
    const earned9000 = calculateGoalPreview(
      { ...payload, earned_ytd_cents: 900_000 },
      0,
    );

    expect(earned3000.deals_remaining).toBe(2);
    expect(earned3000.appointments_remaining).toBe(40);
    expect(earned3000.leads_remaining).toBe(800);
    expect(earned9000.deals_remaining).toBe(1);
    expect(earned9000.appointments_remaining).toBe(6);
    expect(earned9000.leads_remaining).toBe(115);
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
        overage_leads: 0,
        estimated_cost_per_lead_cents: 100,
        state_limit: null,
        features: null,
        recommended: false,
      },
      450,
    );

    expect(recommendation.packages_needed).toBe(3);
    expect(recommendation.total_cost_cents).toBe(60_000);
    expect(recommendation.overage_leads).toBe(150);
    expect(recommendation.estimated_cost_per_lead_cents).toBe(100);
  });

  it("maps Buy Leads catalog amounts into goal recommendations", () => {
    const recommendation = packageCatalogToGoalRecommendation({
      id: 22,
      name: "Growth Live",
      price_cents: 20_000,
      currency: "USD",
      state_limit: null,
      daily_download_limit: 4,
      credits_total: 250,
      features: ["250 leads"],
      stripe_price_id: "price_growth_live",
      created_at: "2026-01-01T00:00:00Z",
    });

    expect(recommendation.package_id).toBe(22);
    expect(recommendation.price_cents).toBe(20_000);
    expect(recommendation.credits_per_package).toBe(250);
  });

  it("falls back to feature credit metadata when the package API omits credits_total", () => {
    const recommendation = packageCatalogToGoalRecommendation({
      id: 23,
      name: "Legacy Growth",
      price_cents: 20_000,
      currency: "USD",
      state_limit: null,
      daily_download_limit: 4,
      features: { credits_total: 200, catalog_visible: true },
      stripe_price_id: "price_legacy_growth",
      created_at: "2026-01-01T00:00:00Z",
    });

    expect(recommendation.credits_per_package).toBe(200);
  });

  it("scores recommendations by cost, overage, package count, and package ID", () => {
    const ranked = rankPackageRecommendations(
      [
        recommendationFixture({
          package_id: 10,
          name: "Larger overage",
          price_cents: 100,
          credits_per_package: 100,
        }),
        recommendationFixture({
          package_id: 8,
          name: "Exact fit",
          price_cents: 100,
          credits_per_package: 95,
        }),
        recommendationFixture({
          package_id: 9,
          name: "Exact fit later",
          price_cents: 100,
          credits_per_package: 95,
        }),
      ],
      95,
    );

    expect(ranked.map((item) => item.package_id)).toEqual([8, 9, 10]);
    expect(ranked[0].recommended).toBe(true);
    expect(ranked[0].overage_leads).toBe(0);
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

const recommendationFixture = (
  overrides: Partial<ReturnType<typeof recalculatePackageRecommendation>>,
) => ({
  package_id: 1,
  name: "Package",
  price_cents: 10_000,
  currency: "USD",
  credits_per_package: 100,
  packages_needed: 1,
  total_cost_cents: 10_000,
  overage_leads: 0,
  estimated_cost_per_lead_cents: 100,
  state_limit: null,
  features: null,
  recommended: false,
  ...overrides,
});
