import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import {
  adminLicenseDecisionRowSchema,
  licenseSchema,
  licenseWithUserSchema,
} from "@/api/license-contract";
import { normalizeQueryParams } from "@/api/query-params";
import type {
  AdminPlanCreatePayload,
  AdminPlanFilters,
  AdminPlanItem,
  AdminPlanUpdatePayload,
  AdminAnalyticsOverview,
  AuditLogFilters,
  DashboardStats,
  DeactivateUserRequest,
  LeadBulkImportSchema,
  LeadInventoryFilters,
  LeadBulkImportResult,
  LicenseStatusSummaryItem,
    PaginatedAdminPlans,
    PaginatedAuditLogs,
    PaginatedLeadInventory,
    PaginatedOrders,
    PaginatedUserDownloadHistory,
    PaginatedUserLicenses,
    PaginatedUserPurchaseHistory,
    PaginatedUserRecentActivity,
    PaginatedUsers,
    UserDetails,
    UserListFilters,
} from "@/types/admin";
import type {
  FirstPurchaseAddonOfferConfig,
  FirstPurchaseAddonOfferUpdatePayload,
} from "@/types/purchase";
import type {
  AdminLicenseDecisionRow,
  License,
  LicenseWithUser,
} from "@/types/license";
import { z } from "zod";

interface LicenseRejectPayload {
  rejection_reason: string;
}

interface LicenseDocumentDownload {
  blob: Blob;
  filename: string;
}

interface LicenseDocumentPreview {
  blob: Blob;
  contentType: string;
}

interface OrdersExportDownload {
  blob: Blob;
  filename: string;
}

interface RequestOptions {
  signal?: AbortSignal;
}

export interface AnalyticsOverviewQuery extends RequestOptions {
  monthlyRevenueLimit?: number;
  userGrowthPage?: number;
  userGrowthSize?: number;
}

const parseFilename = (
  contentDisposition: string | undefined,
  fallback: string,
): string => {
  if (!contentDisposition) {
    return fallback;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]).trim();
  }

  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1].trim();
  }

  return fallback;
};

const dashboardStatsSchema: z.ZodType<DashboardStats> = z
  .looseObject({
    total_users: z.number(),
    completed_purchases: z.number(),
    advisors_with_credits: z.number(),
    pending_licenses: z.number(),
    total_leads: z.number(),
    total_revenue_cents: z.number(),
    currency: z.string(),
  });

const firstPurchaseOfferConfigSchema: z.ZodType<FirstPurchaseAddonOfferConfig> = z
  .looseObject({
    id: z.number().nullable(),
    is_enabled: z.boolean(),
    trigger_package_id: z.number().nullable(),
    trigger_package_name: z.string().nullable(),
    offer_package_id: z.number().nullable(),
    offer_package_name: z.string().nullable(),
    offer_price_cents: z.number().nullable(),
    offer_currency: z.string().nullable(),
    offer_credits_total: z.number().nullable(),
    headline: z.string().nullable(),
    message: z.string().nullable(),
    cta_label: z.string().nullable(),
    starts_at: z.string().nullable(),
    ends_at: z.string().nullable(),
    updated_at: z.string().nullable(),
    updated_by: z.number().nullable(),
    inventory_ready: z.boolean().nullable().optional(),
    inventory_available_count: z.number().nullable().optional(),
    inventory_required_count: z.number().nullable().optional(),
    inventory_gate_code: z.string().nullable().optional(),
    inventory_gate_message: z.string().nullable().optional(),
  });

const adminAnalyticsOverviewSchema: z.ZodType<AdminAnalyticsOverview> = z
  .looseObject({
    monthly_revenue: z.array(
      z
        .looseObject({
          month: z.string(),
          revenue_cents: z.number(),
        }),
    ),
    monthly_revenue_total_months: z.number(),
    plan_breakdown: z.array(
      z
        .looseObject({
          package_name: z.string(),
          purchases: z.number(),
          credits_granted: z.number(),
          credits_remaining: z.number(),
          revenue_cents: z.number(),
        }),
    ),
    state_distribution: z.array(
      z
        .looseObject({
          state_code: z.string(),
          lead_count: z.number(),
        }),
    ),
    user_growth: z.array(
      z
        .looseObject({
          month: z.string(),
          new_users: z.number(),
        }),
    ),
    user_growth_total_months: z.number(),
    user_growth_page: z.number(),
    user_growth_size: z.number(),
    user_growth_total_pages: z.number(),
  });

const adminUserListItemSchema = z
  .looseObject({
    id: z.number(),
    name: z.string(),
    email: z.string(),
    role: z.string(),
    is_active: z.boolean(),
    created_at: z.string(),
    license_count: z.number(),
    current_credits: z.number(),
    total_purchases: z.number(),
  });

const paginatedUsersSchema: z.ZodType<PaginatedUsers> = z
  .looseObject({
    items: z.array(adminUserListItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const adminOrderListItemSchema = z
  .looseObject({
    id: z.number(),
    order_reference: z.string(),
    advisor_name: z.string(),
    advisor_email: z.string(),
    package_name: z.string().nullable(),
    quantity: z.number().nullable(),
    remaining_credits: z.number().nullable(),
    status: z.string(),
    created_at: z.string(),
    amount_cents: z.number(),
    currency: z.string(),
  });

const paginatedOrdersSchema: z.ZodType<PaginatedOrders> = z
  .looseObject({
    items: z.array(adminOrderListItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const adminLeadInventoryItemSchema = z
  .looseObject({
    id: z.number(),
    state_code: z.string(),
    first_name: z.string().nullable(),
    last_name: z.string().nullable(),
    mobile_phone: z.string().nullable(),
    source: z.string().nullable(),
    created_at: z.string(),
    download_count: z.number(),
    assigned_advisor_id: z.number().nullable(),
    assigned_advisor_name: z.string().nullable(),
    assigned_advisor_email: z.string().nullable(),
    purchase_id: z.number().nullable(),
    purchase_reference: z.string().nullable(),
  });

const paginatedLeadInventorySchema: z.ZodType<PaginatedLeadInventory> = z
  .looseObject({
    items: z.array(adminLeadInventoryItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const licenseStatusSummarySchema: z.ZodType<LicenseStatusSummaryItem[]> = z.array(
  z
    .looseObject({
      status: z.enum(["pending", "verified", "rejected"]),
      count: z.number(),
    }),
);

const auditLogSchema = z
  .looseObject({
    id: z.number(),
    actor_user_id: z.number().nullable(),
    actor_name: z.string().nullable().optional(),
    actor_email: z.string().nullable().optional(),
    action: z.string(),
    entity_type: z.string(),
    entity_id: z.number().nullable(),
    meta_data: z.record(z.string(), z.unknown()).nullable(),
    ip_address: z.string().nullable(),
    created_at: z.string(),
  });

const userLicenseItemSchema = z
  .looseObject({
    id: z.number(),
    state: z.string(),
    license_number: z.string(),
    license_type: z.string().nullable(),
    verification_status: z.enum(["pending", "verified", "rejected"]),
    created_at: z.string(),
    verified_at: z.string().nullable(),
    rejection_reason: z.string().nullable(),
  });

const userCreditSummarySchema = z
  .looseObject({
    total_credits: z.number(),
    remaining_credits: z.number(),
    completed_purchases: z.number(),
  });

const userPurchaseItemSchema = z
  .looseObject({
    id: z.number(),
    order_reference: z.string(),
    status: z.string(),
    package_name: z.string().nullable(),
    amount_cents: z.number(),
    currency: z.string(),
    credits_total: z.number(),
    credits_remaining: z.number(),
    purchased_at: z.string(),
  });

const userDownloadHistoryItemSchema = z
  .looseObject({
    lead_id: z.number(),
    state_code: z.string(),
    downloaded_at: z.string(),
    csv_batch_id: z.string().nullable(),
  });

const userHistoryPreviewSchema = <TItem extends z.ZodTypeAny>(itemSchema: TItem) =>
  z.looseObject({
    items: z.array(itemSchema),
    total: z.number(),
    has_more: z.boolean(),
  });

const userDetailsSchema: z.ZodType<UserDetails> = z
  .looseObject({
    id: z.number(),
    name: z.string(),
    email: z.string(),
    role: z.string(),
    is_active: z.boolean(),
    created_at: z.string(),
    deactivated_at: z.string().nullable(),
    deactivated_by: z.number().nullable(),
    credit_summary: userCreditSummarySchema,
    licenses_preview: userHistoryPreviewSchema(userLicenseItemSchema),
    purchase_history_preview: userHistoryPreviewSchema(userPurchaseItemSchema),
    download_history_preview: userHistoryPreviewSchema(userDownloadHistoryItemSchema),
    recent_activity_preview: userHistoryPreviewSchema(auditLogSchema),
  });

const paginatedAuditLogsSchema: z.ZodType<PaginatedAuditLogs> = z
  .looseObject({
    items: z.array(auditLogSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const paginatedUserLicensesSchema: z.ZodType<PaginatedUserLicenses> = z
  .looseObject({
    items: z.array(userLicenseItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const paginatedUserPurchaseHistorySchema: z.ZodType<PaginatedUserPurchaseHistory> = z
  .looseObject({
    items: z.array(userPurchaseItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const paginatedUserDownloadHistorySchema: z.ZodType<PaginatedUserDownloadHistory> = z
  .looseObject({
    items: z.array(userDownloadHistoryItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const paginatedUserRecentActivitySchema: z.ZodType<PaginatedUserRecentActivity> = z
  .looseObject({
    items: z.array(auditLogSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const leadBulkImportResultSchema: z.ZodType<LeadBulkImportResult> = z
  .looseObject({
    success: z.number(),
    failed: z.number(),
    errors: z.array(
      z
        .looseObject({
          row: z.number(),
          error: z.string(),
        }),
    ),
  });

const leadBulkImportSchemaSchema: z.ZodType<LeadBulkImportSchema> = z
  .looseObject({
    headers: z.array(z.string()),
    required_values: z.array(z.string()),
    system_fields: z
      .looseObject({
        source: z.string(),
      }),
  });

const deactivateAdminUserResponseSchema = z
  .looseObject({
    detail: z.string(),
  });

const adminPlanItemSchema: z.ZodType<AdminPlanItem> = z
  .looseObject({
    id: z.number(),
    name: z.string(),
    price_cents: z.number(),
    currency: z.string(),
    stripe_product_id: z.string().nullable(),
    stripe_price_id: z.string(),
    state_limit: z.number().nullable(),
    credits_total: z.number(),
    catalog_visible: z.boolean(),
    is_archived: z.boolean(),
    archived_at: z.string().nullable(),
    effective_from: z.string().nullable(),
    effective_to: z.string().nullable(),
    created_at: z.string(),
    updated_at: z.string().nullable(),
    updated_by: z.number().nullable(),
    has_purchases: z.boolean(),
  });

const paginatedAdminPlansSchema: z.ZodType<PaginatedAdminPlans> = z
  .looseObject({
    items: z.array(adminPlanItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

export const getDashboardStats = async (
  options: RequestOptions = {},
): Promise<DashboardStats> => {
  const response = await apiClient.get<DashboardStats>("/admin/dashboard", {
    signal: options.signal,
  });
  return parseApiContract(
    dashboardStatsSchema,
    response.data,
    "/admin/dashboard",
  );
};

export const getFirstPurchaseOfferConfig = async (): Promise<FirstPurchaseAddonOfferConfig> => {
  const response = await apiClient.get<FirstPurchaseAddonOfferConfig>(
    "/admin/first-purchase-offer",
  );
  return parseApiContract(
    firstPurchaseOfferConfigSchema,
    response.data,
    "/admin/first-purchase-offer",
  );
};

export const updateFirstPurchaseOfferConfig = async (
  payload: FirstPurchaseAddonOfferUpdatePayload,
): Promise<FirstPurchaseAddonOfferConfig> => {
  const response = await apiClient.put<FirstPurchaseAddonOfferConfig>(
    "/admin/first-purchase-offer",
    payload,
  );
  return parseApiContract(
    firstPurchaseOfferConfigSchema,
    response.data,
    "/admin/first-purchase-offer",
  );
};

export const getAnalyticsOverview = async (
  options: AnalyticsOverviewQuery = {},
): Promise<AdminAnalyticsOverview> => {
  const params = normalizeQueryParams({
    monthly_revenue_limit: options.monthlyRevenueLimit,
    user_growth_page: options.userGrowthPage,
    user_growth_size: options.userGrowthSize,
  });
  const response = await apiClient.get<AdminAnalyticsOverview>("/admin/analytics", {
    params,
    signal: options.signal,
  });
  return parseApiContract(
    adminAnalyticsOverviewSchema,
    response.data,
    "/admin/analytics",
  );
};

export const getAdminPlans = async (
  page: number,
  size: number,
  filters: AdminPlanFilters = {},
): Promise<PaginatedAdminPlans> => {
  const params = normalizeQueryParams({
    page,
    size,
    search: filters.search,
    archived: filters.archived,
    effective_at: filters.effective_at,
  });

  const response = await apiClient.get<PaginatedAdminPlans>("/admin/plans", {
    params,
  });
  return parseApiContract(
    paginatedAdminPlansSchema,
    response.data,
    "/admin/plans",
  );
};

export const createAdminPlan = async (
  payload: AdminPlanCreatePayload,
): Promise<AdminPlanItem> => {
  const requestPayload: Record<string, unknown> = {
    name: payload.name.trim(),
    price_cents: payload.price_cents,
    credits_total: payload.credits_total,
    catalog_visible: payload.catalog_visible,
    request_id: payload.request_id.trim(),
  };
  if ("state_limit" in payload) {
    requestPayload.state_limit = payload.state_limit ?? null;
  }
  if ("effective_from" in payload) {
    requestPayload.effective_from = payload.effective_from ?? null;
  }
  if ("effective_to" in payload) {
    requestPayload.effective_to = payload.effective_to ?? null;
  }

  const response = await apiClient.post<AdminPlanItem>(
    "/admin/plans",
    requestPayload,
  );
  return parseApiContract(adminPlanItemSchema, response.data, "/admin/plans");
};

export const updateAdminPlan = async (
  planId: number,
  payload: AdminPlanUpdatePayload,
): Promise<AdminPlanItem> => {
  const requestPayload: Record<string, unknown> = {};
  if ("name" in payload && payload.name !== undefined) {
    requestPayload.name = payload.name.trim();
  }
  if ("price_cents" in payload && payload.price_cents !== undefined) {
    requestPayload.price_cents = payload.price_cents;
  }
  if ("credits_total" in payload && payload.credits_total !== undefined) {
    requestPayload.credits_total = payload.credits_total;
  }
  if ("state_limit" in payload) {
    requestPayload.state_limit = payload.state_limit ?? null;
  }
  if ("catalog_visible" in payload && payload.catalog_visible !== undefined) {
    requestPayload.catalog_visible = payload.catalog_visible;
  }
  if ("effective_from" in payload) {
    requestPayload.effective_from = payload.effective_from ?? null;
  }
  if ("effective_to" in payload) {
    requestPayload.effective_to = payload.effective_to ?? null;
  }
  if ("request_id" in payload && payload.request_id !== undefined) {
    requestPayload.request_id = payload.request_id.trim();
  }

  const response = await apiClient.put<AdminPlanItem>(
    `/admin/plans/${planId}`,
    requestPayload,
  );
  return parseApiContract(
    adminPlanItemSchema,
    response.data,
    `/admin/plans/${planId}`,
  );
};

export const archiveAdminPlan = async (
  planId: number,
  reason?: string,
): Promise<AdminPlanItem> => {
  const payload = normalizeQueryParams({ reason });
  const response = await apiClient.post<AdminPlanItem>(
    `/admin/plans/${planId}/archive`,
    payload,
  );
  return parseApiContract(
    adminPlanItemSchema,
    response.data,
    `/admin/plans/${planId}/archive`,
  );
};

export const unarchiveAdminPlan = async (
  planId: number,
  reason?: string,
): Promise<AdminPlanItem> => {
  const payload = normalizeQueryParams({ reason });
  const response = await apiClient.post<AdminPlanItem>(
    `/admin/plans/${planId}/unarchive`,
    payload,
  );
  return parseApiContract(
    adminPlanItemSchema,
    response.data,
    `/admin/plans/${planId}/unarchive`,
  );
};

export const getUsers = async (
  page: number,
  size: number,
  filters?: UserListFilters,
  options: RequestOptions = {},
): Promise<PaginatedUsers> => {
  const params = normalizeQueryParams({
    page,
    size,
    search: filters?.search,
    role: filters?.role,
    status: filters?.status,
  });

  const response = await apiClient.get<PaginatedUsers>("/admin/users", {
    params,
    signal: options.signal,
  });
  return parseApiContract(
    paginatedUsersSchema,
    response.data,
    "/admin/users",
  );
};

export const getOrders = async (
  page: number,
  size: number,
  status?: string,
  options: RequestOptions = {},
): Promise<PaginatedOrders> => {
  const params = normalizeQueryParams({
    page,
    size,
    status,
  });

  const response = await apiClient.get<PaginatedOrders>("/admin/orders", {
    params,
    signal: options.signal,
  });
  return parseApiContract(
    paginatedOrdersSchema,
    response.data,
    "/admin/orders",
  );
};

export const downloadOrdersExport = async (
  status?: string,
): Promise<OrdersExportDownload> => {
  const params = normalizeQueryParams({ status });
  const response = await apiClient.get<Blob>("/admin/orders/export", {
    params,
    responseType: "blob",
  });
  if (!(response.data instanceof Blob)) {
    throw new TypeError("Unexpected response format from /admin/orders/export");
  }
  const fallback = `admin_orders_${new Date().toISOString().slice(0, 10)}.csv`;
  const filename = parseFilename(
    response.headers["content-disposition"],
    fallback,
  );
  return {
    blob: response.data,
    filename,
  };
};

export const getLeadInventory = async (
  page: number,
  size: number,
  filters: LeadInventoryFilters = {},
  options: RequestOptions = {},
): Promise<PaginatedLeadInventory> => {
  const params = normalizeQueryParams({
    page,
    size,
    search: filters.search,
    state_code: filters.state_code?.toUpperCase(),
    source: filters.source,
    delivery_status: filters.delivery_status,
    created_from: filters.created_from,
    created_to: filters.created_to,
  });

  const response = await apiClient.get<PaginatedLeadInventory>("/admin/lead-inventory", {
    params,
    signal: options.signal,
  });
  return parseApiContract(
    paginatedLeadInventorySchema,
    response.data,
    "/admin/lead-inventory",
  );
};

export const getLicenseStatusSummary = async (
  options: RequestOptions = {},
): Promise<LicenseStatusSummaryItem[]> => {
  const response = await apiClient.get<LicenseStatusSummaryItem[]>(
    "/admin/license-status-summary",
    { signal: options.signal },
  );
  return parseApiContract(
    licenseStatusSummarySchema,
    response.data,
    "/admin/license-status-summary",
  );
};

export const getUser = async (userId: number): Promise<UserDetails> => {
  const response = await apiClient.get<UserDetails>(`/admin/users/${userId}`);
  return parseApiContract(
    userDetailsSchema,
    response.data,
    `/admin/users/${userId}`,
  );
};

const getUserHistorySection = async <TResponse>(
  path: string,
  page: number,
  size: number,
  schema: z.ZodType<TResponse>,
): Promise<TResponse> => {
  const params = normalizeQueryParams({ page, size });
  const response = await apiClient.get<TResponse>(path, { params });
  return parseApiContract(schema, response.data, path);
};

export const getUserLicenses = async (
  userId: number,
  page: number,
  size: number,
): Promise<PaginatedUserLicenses> => {
  return getUserHistorySection(
    `/admin/users/${userId}/licenses`,
    page,
    size,
    paginatedUserLicensesSchema,
  );
};

export const getUserPurchaseHistory = async (
  userId: number,
  page: number,
  size: number,
): Promise<PaginatedUserPurchaseHistory> => {
  return getUserHistorySection(
    `/admin/users/${userId}/purchase-history`,
    page,
    size,
    paginatedUserPurchaseHistorySchema,
  );
};

export const getUserDownloadHistory = async (
  userId: number,
  page: number,
  size: number,
): Promise<PaginatedUserDownloadHistory> => {
  return getUserHistorySection(
    `/admin/users/${userId}/download-history`,
    page,
    size,
    paginatedUserDownloadHistorySchema,
  );
};

export const getUserRecentActivity = async (
  userId: number,
  page: number,
  size: number,
): Promise<PaginatedUserRecentActivity> => {
  return getUserHistorySection(
    `/admin/users/${userId}/recent-activity`,
    page,
    size,
    paginatedUserRecentActivitySchema,
  );
};

const postUserDeactivation = async (
  userId: number,
  payload: DeactivateUserRequest,
): Promise<{ detail: string }> => {
  const normalizedPayload = normalizeQueryParams({
    reason: payload.reason,
  }) as DeactivateUserRequest;

  const response = await apiClient.post<{ detail: string }>(
    `/admin/users/${userId}/deactivate`,
    normalizedPayload,
  );
  return parseApiContract(
    deactivateAdminUserResponseSchema,
    response.data,
    `/admin/users/${userId}/deactivate`,
  );
};

export const deactivateUser = async (
  userId: number,
  reason?: string,
): Promise<void> => {
  await postUserDeactivation(userId, { reason });
};

export const getAuditLogs = async (
  filters: AuditLogFilters,
  page: number,
  size: number,
  options: RequestOptions = {},
): Promise<PaginatedAuditLogs> => {
  const params = normalizeQueryParams({
    page,
    size,
    action: filters.action,
    actor_user_id: filters.actor_user_id,
    entity_type: filters.entity_type,
    entity_id: filters.entity_id,
    created_from: filters.created_from,
    created_to: filters.created_to,
  });

  const response = await apiClient.get<PaginatedAuditLogs>("/admin/audit-logs", {
    params,
    signal: options.signal,
  });
  return parseApiContract(
    paginatedAuditLogsSchema,
    response.data,
    "/admin/audit-logs",
  );
};

export const bulkImportLeadsAsAdmin = async (
  csvFile: File,
): Promise<LeadBulkImportResult> => {
  const formData = new FormData();
  formData.append("csv_file", csvFile);

  const response = await apiClient.post<LeadBulkImportResult>("/leads/bulk", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return parseApiContract(
    leadBulkImportResultSchema,
    response.data,
    "/leads/bulk",
  );
};

export const getLeadBulkImportSchemaAsAdmin = async (): Promise<LeadBulkImportSchema> => {
  const response = await apiClient.get<LeadBulkImportSchema>("/leads/bulk/schema");
  return parseApiContract(
    leadBulkImportSchemaSchema,
    response.data,
    "/leads/bulk/schema",
  );
};

export const getPendingLicenses = async (): Promise<LicenseWithUser[]> => {
  const response = await apiClient.get<LicenseWithUser[]>("/licenses/pending");
  return parseApiContract(
    z.array(licenseWithUserSchema),
    response.data,
    "/licenses/pending",
  );
};

export const getAdminDashboardStats = getDashboardStats;

interface GetAdminUsersParams {
  page?: number;
  size?: number;
  filters?: UserListFilters;
}

export const getAdminUsers = async (
  params: GetAdminUsersParams = {},
): Promise<PaginatedUsers> => {
  return getUsers(params.page ?? 1, params.size ?? 20, params.filters);
};

export const getAdminUserDetails = getUser;

export const deactivateAdminUser = async (
  userId: number,
  payload: DeactivateUserRequest,
): Promise<{ detail: string }> => {
  return postUserDeactivation(userId, payload);
};

interface GetAuditLogsParams {
  page?: number;
  size?: number;
  filters?: AuditLogFilters;
}

export const getAdminAuditLogs = async (
  params: GetAuditLogsParams = {},
): Promise<PaginatedAuditLogs> => {
  return getAuditLogs(params.filters ?? {}, params.page ?? 1, params.size ?? 20);
};

interface GetProcessedLicensesParams {
  advisorId?: number;
  advisorQuery?: string;
}

export const getProcessedLicenses = async (
  params: GetProcessedLicensesParams = {},
): Promise<AdminLicenseDecisionRow[]> => {
  const response = await apiClient.get<AdminLicenseDecisionRow[]>("/licenses/processed", {
    params: {
      advisor_id: params.advisorId,
      advisor_query: params.advisorQuery,
    },
  });
  return parseApiContract(
    z.array(adminLicenseDecisionRowSchema),
    response.data,
    "/licenses/processed",
  );
};

export const approveLicense = async (licenseId: number): Promise<License> => {
  const response = await apiClient.post<License>(`/licenses/${licenseId}/approve`);
  return parseApiContract(
    licenseSchema,
    response.data,
    `/licenses/${licenseId}/approve`,
  );
};

export const rejectLicense = async (
  licenseId: number,
  rejectionReason: string,
): Promise<License> => {
  const payload: LicenseRejectPayload = {
    rejection_reason: rejectionReason.trim(),
  };

  const response = await apiClient.post<License>(
    `/licenses/${licenseId}/reject`,
    payload,
  );
  return parseApiContract(
    licenseSchema,
    response.data,
    `/licenses/${licenseId}/reject`,
  );
};

export const downloadLicenseDocument = async (
  licenseId: number,
): Promise<LicenseDocumentDownload> => {
  const response = await apiClient.get<Blob>(`/licenses/${licenseId}/document`, {
    responseType: "blob",
  });
  if (!(response.data instanceof Blob)) {
    throw new TypeError(
      `Unexpected response format from /licenses/${licenseId}/document`,
    );
  }

  const fallback = `license_${licenseId}`;
  const filename = parseFilename(
    response.headers["content-disposition"],
    fallback,
  );

  return {
    blob: response.data,
    filename,
  };
};

export const previewLicenseDocument = async (
  licenseId: number,
): Promise<LicenseDocumentPreview> => {
  const response = await apiClient.get<Blob>(`/licenses/${licenseId}/document`, {
    params: { access_mode: "preview" },
    responseType: "blob",
  });
  if (!(response.data instanceof Blob)) {
    throw new TypeError(
      `Unexpected response format from /licenses/${licenseId}/document`,
    );
  }

  return {
    blob: response.data,
    contentType: (response.headers["content-type"] || "").toLowerCase(),
  };
};
