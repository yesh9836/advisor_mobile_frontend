export type LeadSource =
  | "wordpress_import"
  | "manual_entry"
  | "api_submission"
  | "csv_import"
  | (string & {});

export type LeadOutcomeStatus =
  | "new"
  | "contacted"
  | "appointment_set"
  | "closed_deal"
  | (string & {});

export interface Lead {
  id: number;
  source: LeadSource | null;

  state_code: string;
  zip_code: string | null;

  first_name: string | null;
  last_name: string | null;
  mobile_phone: string | null;
  preferred_follow_up_method: string | null;
  best_time_to_reach: string | null;

  retirement_timeline: string | null;
  confidence_in_long_term_plan: string | null;
  most_important_retirement_activity: string | null;
  planning_to_relocate_retirement: string | null;
  expected_retirement_income_source: string | null;

  overall_health: string | null;
  money_management_style: string | null;
  investor_profile_statement: string | null;
  investment_comfort_level: string | null;
  main_purpose_for_investing: string[] | null;

  retirement_savings_range: string | null;
  annual_household_income_range: string | null;
  total_investable_assets_range: string | null;
  monthly_savings_range: string | null;
  wants_to_improve_strategy_timing: string | null;

  current_investment_strategies: string[] | null;
  has_financial_advisor: string | null;
  advisor_local_preference: string | null;
  owns_annuity: string | null;

  additional_notes: string | null;

  created_at: string;
  received_at?: string | null;
  updated_at?: string | null;

  outcome_status?: LeadOutcomeStatus | null;
  outcome_notes?: string | null;
  outcome_updated_at?: string | null;
  is_downloaded?: boolean;
  downloaded_at?: string | null;
  pii_unlocked?: boolean;
}

export interface LeadFilters {
  delivery_status?: "all" | "available" | "delivered";
  outcome_status?: "all" | "new" | "contacted" | "appointment_set" | "closed_deal";
  state_code?: string;
  zip_code?: string;
  retirement_timeline?: string;
  total_investable_assets_range?: string;
  has_financial_advisor?: string;
  created_from?: string;
  created_to?: string;
  search?: string;
}

export interface PaginatedLeads {
  items: Lead[];
  total: number;
  page: number;
  size: number;
}

export interface LeadOutcomeUpdatePayload {
  status: LeadOutcomeStatus;
  notes: string | null;
}

export interface LeadOutcome {
  id: number;
  user_id: number;
  lead_id: number;
  status: LeadOutcomeStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DashboardSettingsSnapshot {
  email_alerts_enabled: boolean;
  sms_alerts_enabled: boolean;
  target_states: string[];
  min_assets: string | null;
  daily_download_limit: number | null;
}

export interface LeadDashboardSummary {
  leads_delivered_7_days: number;
  appointments_set_7_days: number;
  cost_per_appointment: number;
  currency: string;
  settings: DashboardSettingsSnapshot;
}
