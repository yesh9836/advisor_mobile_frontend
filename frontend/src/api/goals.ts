import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import type {
  AdvisorGoalResponse,
  AdvisorGoalUpdatePayload,
  GoalDerived,
  GoalPackageRecommendation,
  GoalPacing,
} from "@/types/goal";
import { z } from "zod";

interface RequestOptions {
  signal?: AbortSignal;
}

const featuresSchema = z.union([
  z.array(z.string()),
  z.record(z.string(), z.unknown()),
  z.null(),
]);

const goalPacingSchema: z.ZodType<GoalPacing> = z.looseObject({
  remaining_months: z.number(),
  recommended_monthly_leads: z.number(),
  status: z.string(),
  message: z.string(),
});

const goalDerivedSchema: z.ZodType<GoalDerived> = z.looseObject({
  deals_needed: z.number(),
  appointments_needed: z.number(),
  leads_needed: z.number(),
  closed_deals_ytd: z.number(),
  estimated_deals_from_earned_ytd: z.number(),
  income_progress_percent: z.number(),
  deals_remaining: z.number(),
  appointments_remaining: z.number(),
  leads_remaining: z.number(),
  recommended_monthly_leads: z.number(),
  pacing: goalPacingSchema,
});

const goalPackageRecommendationSchema: z.ZodType<GoalPackageRecommendation> =
  z.looseObject({
    package_id: z.number(),
    name: z.string(),
    price_cents: z.number(),
    currency: z.string(),
    credits_per_package: z.number(),
    packages_needed: z.number(),
    total_cost_cents: z.number(),
    estimated_cost_per_lead_cents: z.number(),
    state_limit: z.number().nullable(),
    features: featuresSchema,
    recommended: z.boolean(),
  });

const advisorGoalResponseSchema: z.ZodType<AdvisorGoalResponse> = z.looseObject({
  goal: z.looseObject({
    id: z.number(),
    user_id: z.number(),
    target_year: z.number(),
    annual_income_goal_cents: z.number(),
    average_commission_cents: z.number(),
    earned_ytd_cents: z.number(),
    appointment_to_deal_rate_bps: z.number(),
    lead_to_appointment_rate_bps: z.number(),
    created_at: z.string(),
    updated_at: z.string(),
  }),
  derived: goalDerivedSchema,
  packages: z.array(goalPackageRecommendationSchema),
});

export const getMyGoal = async (
  targetYear?: number,
  options: RequestOptions = {},
): Promise<AdvisorGoalResponse> => {
  const response = await apiClient.get<AdvisorGoalResponse>("/goals/me", {
    params: targetYear ? { target_year: targetYear } : undefined,
    signal: options.signal,
  });
  return parseApiContract(advisorGoalResponseSchema, response.data, "/goals/me");
};

export const saveMyGoal = async (
  payload: AdvisorGoalUpdatePayload,
): Promise<AdvisorGoalResponse> => {
  const response = await apiClient.put<AdvisorGoalResponse>("/goals/me", payload);
  return parseApiContract(advisorGoalResponseSchema, response.data, "/goals/me");
};
