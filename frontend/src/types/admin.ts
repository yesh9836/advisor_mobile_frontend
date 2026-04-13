export interface DashboardStats {
  total_users: number;
  completed_purchases: number;
  advisors_with_credits: number;
  pending_licenses: number;
  total_leads: number;
  total_revenue_cents: number;
  currency: string;
}

export interface MonthlyRevenuePoint {
  month: string;
  revenue_cents: number;
}

export interface PlanBreakdownItem {
  package_name: string;
  purchases: number;
  credits_granted: number;
  credits_remaining: number;
  revenue_cents: number;
}

export interface StateDistributionItem {
  state_code: string;
  lead_count: number;
}

export interface UserGrowthPoint {
  month: string;
  new_users: number;
}

export interface AdminAnalyticsOverview {
  monthly_revenue: MonthlyRevenuePoint[];
  monthly_revenue_total_months: number;
  plan_breakdown: PlanBreakdownItem[];
  state_distribution: StateDistributionItem[];
  user_growth: UserGrowthPoint[];
  user_growth_total_months: number;
  user_growth_page: number;
  user_growth_size: number;
  user_growth_total_pages: number;
}

export interface AdminUserListItem {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  license_count: number;
  current_credits: number;
  total_purchases: number;
}

export interface PaginatedUsers {
  items: AdminUserListItem[];
  total: number;
  page: number;
  size: number;
}

export interface AdminOrderListItem {
  id: number;
  order_reference: string;
  advisor_name: string;
  advisor_email: string;
  package_name: string | null;
  quantity: number | null;
  remaining_credits: number | null;
  status: string;
  created_at: string;
  amount_cents: number;
  currency: string;
}

export interface PaginatedOrders {
  items: AdminOrderListItem[];
  total: number;
  page: number;
  size: number;
}

export interface AdminLeadInventoryItem {
  id: number;
  state_code: string;
  first_name: string | null;
  last_name: string | null;
  mobile_phone: string | null;
  source: string | null;
  created_at: string;
  download_count: number;
  assigned_advisor_id: number | null;
  assigned_advisor_name: string | null;
  assigned_advisor_email: string | null;
  purchase_id: number | null;
  purchase_reference: string | null;
}

export interface PaginatedLeadInventory {
  items: AdminLeadInventoryItem[];
  total: number;
  page: number;
  size: number;
}

export interface LeadInventoryFilters {
  search?: string;
  state_code?: string;
  source?: string;
  delivery_status?: "all" | "unsold" | "sold";
  created_from?: string;
  created_to?: string;
}

export interface LicenseStatusSummaryItem {
  status: "pending" | "verified" | "rejected";
  count: number;
}

export interface AdminLeadCreatePayload {
  state_code: string;
  mobile_phone: string;
  first_name?: string;
  last_name?: string;
  source?: string;
}

export interface UserLicenseItem {
  id: number;
  state: string;
  license_number: string;
  license_type: string | null;
  verification_status: "pending" | "verified" | "rejected";
  created_at: string;
  verified_at: string | null;
  rejection_reason: string | null;
}

export interface UserCreditSummary {
  total_credits: number;
  remaining_credits: number;
  completed_purchases: number;
}

export interface UserPurchaseItem {
  id: number;
  order_reference: string;
  status: string;
  package_name: string | null;
  amount_cents: number;
  currency: string;
  credits_total: number;
  credits_remaining: number;
  purchased_at: string;
}

export interface UserDownloadHistoryItem {
  lead_id: number;
  state_code: string;
  downloaded_at: string;
  csv_batch_id: string | null;
}

export interface AuditLog {
  id: number;
  actor_user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number | null;
  meta_data: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface UserHistoryPreview<TItem> {
  items: TItem[];
  total: number;
  has_more: boolean;
}

export interface UserDetails {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  deactivated_at: string | null;
  deactivated_by: number | null;
  credit_summary: UserCreditSummary;
  licenses_preview: UserHistoryPreview<UserLicenseItem>;
  purchase_history_preview: UserHistoryPreview<UserPurchaseItem>;
  download_history_preview: UserHistoryPreview<UserDownloadHistoryItem>;
  recent_activity_preview: UserHistoryPreview<AuditLog>;
}

export type AuditLogItem = AuditLog;

export interface PaginatedAuditLogs {
  items: AuditLog[];
  total: number;
  page: number;
  size: number;
}

export interface PaginatedUserLicenses {
  items: UserLicenseItem[];
  total: number;
  page: number;
  size: number;
}

export interface PaginatedUserPurchaseHistory {
  items: UserPurchaseItem[];
  total: number;
  page: number;
  size: number;
}

export interface PaginatedUserDownloadHistory {
  items: UserDownloadHistoryItem[];
  total: number;
  page: number;
  size: number;
}

export interface PaginatedUserRecentActivity {
  items: AuditLog[];
  total: number;
  page: number;
  size: number;
}

export interface DeactivateUserRequest {
  reason?: string;
}

export interface UserListFilters {
  search?: string;
  role?: "admin" | "advisor";
  status?: "active" | "inactive";
}

export interface AuditLogFilters {
  action?: string;
  actor_user_id?: number;
  entity_type?: string;
  entity_id?: number;
  created_from?: string;
  created_to?: string;
}

export interface ImportStats {
  scanned: number;
  inserted: number;
  skipped_duplicates: number;
  failed: number;
  errors: Array<{ row?: number; error: string }>;
}

export interface LeadBulkImportResult {
  success: number;
  failed: number;
  errors: Array<{ row: number; error: string }>;
}

export interface LeadBulkImportSchema {
  headers: string[];
  required_values: string[];
  system_fields: {
    source: string;
  };
}

export interface AdminPlanItem {
  id: number;
  name: string;
  price_cents: number;
  currency: string;
  stripe_product_id: string | null;
  stripe_price_id: string;
  state_limit: number | null;
  credits_total: number;
  catalog_visible: boolean;
  is_archived: boolean;
  archived_at: string | null;
  effective_from: string | null;
  effective_to: string | null;
  created_at: string;
  updated_at: string | null;
  updated_by: number | null;
  has_purchases: boolean;
}

export interface PaginatedAdminPlans {
  items: AdminPlanItem[];
  total: number;
  page: number;
  size: number;
}

export interface AdminPlanFilters {
  search?: string;
  archived?: "all" | "archived" | "unarchived";
  effective_at?: string;
}

export interface AdminPlanCreatePayload {
  name: string;
  price_cents: number;
  credits_total: number;
  state_limit?: number | null;
  catalog_visible: boolean;
  effective_from?: string | null;
  effective_to?: string | null;
  request_id: string;
}

export interface AdminPlanUpdatePayload {
  name?: string;
  price_cents?: number;
  credits_total?: number;
  state_limit?: number | null;
  catalog_visible?: boolean;
  effective_from?: string | null;
  effective_to?: string | null;
  request_id?: string;
}
