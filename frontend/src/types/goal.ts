export interface AdvisorGoal {
  id: number;
  user_id: number;
  target_year: number;
  annual_income_goal_cents: number;
  average_commission_cents: number;
  earned_ytd_cents: number;
  appointment_to_deal_rate_bps: number;
  lead_to_appointment_rate_bps: number;
  created_at: string;
  updated_at: string;
}

export interface GoalPacing {
  remaining_months: number;
  recommended_monthly_leads: number;
  status: string;
  message: string;
}

export interface GoalDerived {
  deals_needed: number;
  appointments_needed: number;
  leads_needed: number;
  closed_deals_ytd: number;
  estimated_deals_from_earned_ytd: number;
  income_progress_percent: number;
  deals_remaining: number;
  appointments_remaining: number;
  leads_remaining: number;
  recommended_monthly_leads: number;
  pacing: GoalPacing;
}

export interface GoalPackageRecommendation {
  package_id: number;
  name: string;
  price_cents: number;
  currency: string;
  credits_per_package: number;
  packages_needed: number;
  total_cost_cents: number;
  estimated_cost_per_lead_cents: number;
  state_limit: number | null;
  features: string[] | Record<string, unknown> | null;
  recommended: boolean;
}

export interface AdvisorGoalResponse {
  goal: AdvisorGoal;
  derived: GoalDerived;
  packages: GoalPackageRecommendation[];
}

export interface AdvisorGoalUpdatePayload {
  target_year: number;
  annual_income_goal_cents: number;
  average_commission_cents: number;
  earned_ytd_cents: number;
  appointment_to_deal_rate_bps: number;
  lead_to_appointment_rate_bps: number;
}
