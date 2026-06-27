import type {
  AdvisorGoalUpdatePayload,
  GoalDerived,
  GoalPackageRecommendation,
} from "@/types/goal";
import type { PurchasePackage } from "@/types/purchase";

export const centsToDollarsInput = (cents: number): string => {
  return String(Math.round((cents || 0) / 100));
};

export const basisPointsToPercentInput = (basisPoints: number): string => {
  const value = (basisPoints || 0) / 100;
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
};

export const parseMoneyToCents = (value: string): number | null => {
  const normalized = value.replace(/,/g, "").trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.round(parsed * 100);
};

export const parsePercentToBasisPoints = (value: string): number | null => {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.round(parsed * 100);
};

export const formatWholeMoney = (
  cents: number,
  currency = "USD",
): string => {
  return (Math.max(cents, 0) / 100).toLocaleString("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    maximumFractionDigits: 0,
  });
};

export const formatCompactMoney = (
  cents: number,
  currency = "USD",
): string => {
  return (Math.max(cents, 0) / 100).toLocaleString("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  });
};

export const formatNumber = (value: number): string => {
  return Math.max(Math.round(value), 0).toLocaleString("en-US");
};

export const calculateGoalPreview = (
  payload: AdvisorGoalUpdatePayload,
  closedDealsYtd: number,
): GoalDerived => {
  const annualGoal = Math.max(payload.annual_income_goal_cents, 1);
  const averageCommission = Math.max(payload.average_commission_cents, 1);
  const earnedYtd = Math.max(payload.earned_ytd_cents, 0);
  const closeRate = Math.max(payload.appointment_to_deal_rate_bps, 1) / 10000;
  const appointmentRate = Math.max(payload.lead_to_appointment_rate_bps, 1) / 10000;
  const dealsNeeded = Math.ceil(annualGoal / averageCommission);
  const appointmentsNeeded = Math.ceil(dealsNeeded / closeRate);
  const leadsNeeded = Math.ceil(appointmentsNeeded / appointmentRate);
  const closedDeals = Math.max(Math.round(closedDealsYtd), 0);
  const progressPercent = Math.min(100, Math.round((earnedYtd / annualGoal) * 100));
  const remainingIncome = Math.max(annualGoal - earnedYtd, 0);
  const incomeGoalMet = remainingIncome === 0;
  const remainingDealEquivalent = remainingIncome / averageCommission;
  const dealsRemaining = incomeGoalMet
    ? 0
    : Math.ceil(remainingDealEquivalent);
  const appointmentsRemaining = remainingDealEquivalent
    ? Math.ceil(remainingDealEquivalent / closeRate)
    : 0;
  const leadsRemaining = remainingDealEquivalent
    ? Math.ceil(remainingDealEquivalent / (closeRate * appointmentRate))
    : 0;
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const remainingMonths =
    payload.target_year < currentYear
      ? 1
      : payload.target_year > currentYear
        ? 12
        : Math.max(1, 12 - currentDate.getMonth());
  const monthlyLeads = leadsRemaining
    ? Math.ceil(leadsRemaining / remainingMonths)
    : 0;
  const message = incomeGoalMet
    ? "Annual income goal met."
    : leadsRemaining > 0
      ? `Buy about ${formatNumber(monthlyLeads)} leads/month for the rest of the year.`
      : "Lead volume goal met based on actual closed deals year-to-date.";

  return {
    deals_needed: dealsNeeded,
    appointments_needed: appointmentsNeeded,
    leads_needed: leadsNeeded,
    closed_deals_ytd: closedDeals,
    income_progress_percent: progressPercent,
    deals_remaining: dealsRemaining,
    appointments_remaining: appointmentsRemaining,
    leads_remaining: leadsRemaining,
    recommended_monthly_leads: monthlyLeads,
    pacing: {
      remaining_months: remainingMonths,
      recommended_monthly_leads: monthlyLeads,
      status: incomeGoalMet ? "goal_met" : leadsRemaining > 0 ? "active" : "on_track",
      message,
    },
  };
};

export const recalculatePackageRecommendation = (
  recommendation: GoalPackageRecommendation,
  leadsRemaining: number,
): GoalPackageRecommendation => {
  const targetLeads = Math.max(leadsRemaining, 1);
  const credits = Math.max(recommendation.credits_per_package, 1);
  const packagesNeeded = Math.ceil(targetLeads / credits);
  const coveredLeads = packagesNeeded * credits;
  return {
    ...recommendation,
    packages_needed: packagesNeeded,
    total_cost_cents: packagesNeeded * Math.max(recommendation.price_cents, 0),
    overage_leads: Math.max(coveredLeads - targetLeads, 0),
    estimated_cost_per_lead_cents: Math.ceil(
      Math.max(recommendation.price_cents, 0) / credits,
    ),
  };
};

const resolvePackageCredits = (packageOption: PurchasePackage): number => {
  const directCredits = Math.round(packageOption.credits_total ?? 0);
  if (directCredits > 0) {
    return directCredits;
  }

  if (packageOption.features && !Array.isArray(packageOption.features)) {
    const rawCredits =
      packageOption.features.credits_total ?? packageOption.features.credits;
    if (typeof rawCredits === "number" && Number.isFinite(rawCredits)) {
      return Math.max(Math.round(rawCredits), 0);
    }
    if (typeof rawCredits === "string" && /^\d+$/.test(rawCredits.trim())) {
      return Number(rawCredits.trim());
    }
  }

  return Math.max(Math.round(packageOption.daily_download_limit ?? 0), 0);
};

export const packageCatalogToGoalRecommendation = (
  packageOption: PurchasePackage,
): GoalPackageRecommendation => {
  const credits = resolvePackageCredits(packageOption);
  const priceCents = Math.max(Math.round(packageOption.price_cents ?? 0), 0);
  return {
    package_id: packageOption.id,
    name: packageOption.name,
    price_cents: priceCents,
    currency: packageOption.currency,
    credits_per_package: credits,
    packages_needed: 1,
    total_cost_cents: priceCents,
    overage_leads: 0,
    estimated_cost_per_lead_cents: credits ? Math.ceil(priceCents / credits) : 0,
    state_limit: packageOption.state_limit,
    features: packageOption.features,
    recommended: false,
  };
};

export const rankPackageRecommendations = (
  packages: GoalPackageRecommendation[],
  leadsRemaining: number,
  limit = 3,
): GoalPackageRecommendation[] => {
  if (leadsRemaining <= 0) {
    return [];
  }

  const recalculated = packages
    .filter((item) => item.credits_per_package > 0)
    .map((item) => recalculatePackageRecommendation(item, leadsRemaining));
  const sorted = [...recalculated].sort((left, right) => {
    const leftScore = [
      left.total_cost_cents,
      left.overage_leads,
      left.packages_needed,
      left.package_id,
    ];
    const rightScore = [
      right.total_cost_cents,
      right.overage_leads,
      right.packages_needed,
      right.package_id,
    ];

    for (let index = 0; index < leftScore.length; index += 1) {
      const delta = leftScore[index] - rightScore[index];
      if (delta !== 0) {
        return delta;
      }
    }
    return 0;
  });
  const bestPackageId = sorted[0]?.package_id ?? null;
  return sorted.slice(0, limit).map((item) => ({
    ...item,
    recommended: item.package_id === bestPackageId,
  }));
};
