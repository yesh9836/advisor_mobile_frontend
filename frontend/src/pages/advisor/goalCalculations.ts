import type {
  AdvisorGoalUpdatePayload,
  GoalDerived,
  GoalPackageRecommendation,
} from "@/types/goal";

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
  const estimatedDeals = Math.floor(earnedYtd / averageCommission);
  const progressPercent = Math.min(100, Math.round((earnedYtd / annualGoal) * 100));
  const dealsRemaining = Math.max(dealsNeeded - estimatedDeals, 0);
  const appointmentsRemaining = dealsRemaining
    ? Math.ceil(dealsRemaining / closeRate)
    : 0;
  const leadsRemaining = dealsRemaining
    ? Math.ceil(dealsRemaining / (closeRate * appointmentRate))
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
  const message =
    leadsRemaining > 0
      ? `Buy about ${formatNumber(monthlyLeads)} leads/month for the rest of the year.`
      : "Goal met based on manually entered earned year-to-date.";

  return {
    deals_needed: dealsNeeded,
    appointments_needed: appointmentsNeeded,
    leads_needed: leadsNeeded,
    closed_deals_ytd: closedDealsYtd,
    estimated_deals_from_earned_ytd: estimatedDeals,
    income_progress_percent: progressPercent,
    deals_remaining: dealsRemaining,
    appointments_remaining: appointmentsRemaining,
    leads_remaining: leadsRemaining,
    recommended_monthly_leads: monthlyLeads,
    pacing: {
      remaining_months: remainingMonths,
      recommended_monthly_leads: monthlyLeads,
      status: leadsRemaining > 0 ? "active" : "on_track",
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
  return {
    ...recommendation,
    packages_needed: packagesNeeded,
    total_cost_cents: packagesNeeded * Math.max(recommendation.price_cents, 0),
    estimated_cost_per_lead_cents: Math.ceil(
      Math.max(recommendation.price_cents, 0) / credits,
    ),
  };
};
