import type { License } from "@/types/license";

export interface DashboardStats {
  total_users: number;
  active_subscriptions: number;
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
  plan_name: string;
  active_subscriptions: number;
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
  plan_breakdown: PlanBreakdownItem[];
  state_distribution: StateDistributionItem[];
  user_growth: UserGrowthPoint[];
}

export interface AdminUserListItem {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  license_count: number;
  subscription_status: string | null;
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
  status: string;
  created_at: string;
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

export interface UserSubscriptionItem {
  id: number;
  status: string;
  plan_name: string | null;
  price_cents: number | null;
  currency: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
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

export interface UserDetails {
  id: number;
  name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
  deactivated_at: string | null;
  deactivated_by: number | null;
  licenses: Array<UserLicenseItem | License>;
  subscription: UserSubscriptionItem | null;
  download_history: UserDownloadHistoryItem[];
  recent_activity: AuditLog[];
}

export type AuditLogItem = AuditLog;

export interface PaginatedAuditLogs {
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
