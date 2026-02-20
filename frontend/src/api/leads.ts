import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import type {
  Lead,
  LeadDashboardSummary,
  LeadFilters,
  LeadOutcome,
  LeadOutcomeUpdatePayload,
  PaginatedLeads,
} from "@/types/lead";
import { z } from "zod";

const nullableString = z.string().nullable();
const nullableStringArray = z.array(z.string()).nullable();

export const leadSchema: z.ZodType<Lead> = z
  .object({
    id: z.number(),
    source: z.string().nullable(),
    state_code: z.string(),
    zip_code: nullableString,
    first_name: nullableString,
    last_name: nullableString,
    mobile_phone: nullableString,
    preferred_follow_up_method: nullableString,
    best_time_to_reach: nullableString,
    retirement_timeline: nullableString,
    confidence_in_long_term_plan: nullableString,
    most_important_retirement_activity: nullableString,
    planning_to_relocate_retirement: nullableString,
    expected_retirement_income_source: nullableString,
    overall_health: nullableString,
    money_management_style: nullableString,
    investor_profile_statement: nullableString,
    investment_comfort_level: nullableString,
    main_purpose_for_investing: nullableStringArray,
    retirement_savings_range: nullableString,
    annual_household_income_range: nullableString,
    total_investable_assets_range: nullableString,
    monthly_savings_range: nullableString,
    wants_to_improve_strategy_timing: nullableString,
    current_investment_strategies: nullableStringArray,
    has_financial_advisor: nullableString,
    advisor_local_preference: nullableString,
    owns_annuity: nullableString,
    additional_notes: nullableString,
    created_at: z.string(),
    updated_at: z.string().nullable().optional(),
    outcome_status: z.string().nullable().optional(),
    outcome_notes: z.string().nullable().optional(),
    outcome_updated_at: z.string().nullable().optional(),
    is_downloaded: z.boolean().optional(),
    downloaded_at: z.string().nullable().optional(),
  })
  .passthrough();

const paginatedLeadsSchema: z.ZodType<PaginatedLeads> = z
  .object({
    items: z.array(leadSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  })
  .passthrough();

const leadOutcomeSchema: z.ZodType<LeadOutcome> = z
  .object({
    id: z.number(),
    user_id: z.number(),
    lead_id: z.number(),
    status: z.string(),
    notes: z.string().nullable(),
    created_at: z.string(),
    updated_at: z.string(),
  })
  .passthrough();

const leadDashboardSummarySchema: z.ZodType<LeadDashboardSummary> = z
  .object({
    leads_delivered_7_days: z.number(),
    appointments_set_7_days: z.number(),
    cost_per_appointment: z.number(),
    currency: z.string(),
    settings: z
      .object({
        email_alerts_enabled: z.boolean(),
        sms_alerts_enabled: z.boolean(),
        target_states: z.array(z.string()),
        min_assets: z.string().nullable(),
        daily_download_limit: z.number().nullable(),
      })
      .passthrough(),
  })
  .passthrough();

const normalizeFilters = (filters: LeadFilters): Record<string, string> => {
  const params: Record<string, string> = {};

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }

    const normalized = String(value).trim();
    if (!normalized) {
      return;
    }

    params[key] = normalized;
  });

  return params;
};

export const getLeads = async (
  page: number,
  size: number,
  filters: LeadFilters = {},
): Promise<PaginatedLeads> => {
  const response = await apiClient.get<PaginatedLeads>("/leads", {
    params: {
      page,
      size,
      ...normalizeFilters(filters),
    },
  });

  return parseApiContract(paginatedLeadsSchema, response.data, "/leads");
};

export const downloadLeads = async (): Promise<Blob> => {
  const response = await apiClient.post<Blob>(
    "/leads/download",
    undefined,
    {
      responseType: "blob",
      headers: {
        Accept: "text/csv",
      },
    },
  );

  if (!(response.data instanceof Blob)) {
    throw new TypeError("Unexpected response format from /leads/download");
  }

  return response.data;
};

export const saveLeadOutcome = async (
  leadId: number,
  payload: LeadOutcomeUpdatePayload,
): Promise<LeadOutcome> => {
  const response = await apiClient.put<LeadOutcome>(
    `/leads/${leadId}/outcome`,
    payload,
  );
  return parseApiContract(
    leadOutcomeSchema,
    response.data,
    `/leads/${leadId}/outcome`,
  );
};

export const getLeadDashboardSummary =
  async (): Promise<LeadDashboardSummary> => {
    const response = await apiClient.get<LeadDashboardSummary>(
      "/leads/dashboard/summary",
    );
    return parseApiContract(
      leadDashboardSummarySchema,
      response.data,
      "/leads/dashboard/summary",
    );
  };
