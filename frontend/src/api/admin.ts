import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import {
  adminLicenseDecisionRowSchema,
  licenseSchema,
  licenseWithUserSchema,
} from "@/api/license-contract";
import { leadSchema } from "@/api/leads";
import type {
  AdminAnalyticsOverview,
  AdminLeadCreatePayload,
  AuditLogFilters,
  DashboardStats,
  DeactivateUserRequest,
  ImportStats,
  LeadBulkImportSchema,
  LeadInventoryFilters,
  LeadBulkImportResult,
  LicenseStatusSummaryItem,
  PaginatedAuditLogs,
  PaginatedLeadInventory,
  PaginatedOrders,
  PaginatedUsers,
  UserDetails,
  UserListFilters,
} from "@/types/admin";
import type { Lead } from "@/types/lead";
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

type QueryParamValue = string | number | boolean | null | undefined;

const normalizeParams = <T extends Record<string, QueryParamValue>>(
  params: T,
): Partial<Record<keyof T, string | number | boolean>> => {
  const cleanedEntries = Object.entries(params).flatMap(([key, value]) => {
    if (value === undefined || value === null) {
      return [];
    }

    if (typeof value === "string") {
      const trimmed = value.trim();
      if (!trimmed) {
        return [];
      }
      return [[key, trimmed]];
    }

    return [[key, value]];
  });

  return Object.fromEntries(cleanedEntries) as Partial<
    Record<keyof T, string | number | boolean>
  >;
};

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
  .object({
    total_users: z.number(),
    completed_purchases: z.number(),
    advisors_with_credits: z.number(),
    pending_licenses: z.number(),
    total_leads: z.number(),
    total_revenue_cents: z.number(),
    currency: z.string(),
  })
  .passthrough();

const firstPurchaseOfferConfigSchema: z.ZodType<FirstPurchaseAddonOfferConfig> = z
  .object({
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
  })
  .passthrough();

const adminAnalyticsOverviewSchema: z.ZodType<AdminAnalyticsOverview> = z
  .object({
    monthly_revenue: z.array(
      z
        .object({
          month: z.string(),
          revenue_cents: z.number(),
        })
        .passthrough(),
    ),
    plan_breakdown: z.array(
      z
        .object({
          package_name: z.string(),
          purchases: z.number(),
          credits_granted: z.number(),
          credits_remaining: z.number(),
          revenue_cents: z.number(),
        })
        .passthrough(),
    ),
    state_distribution: z.array(
      z
        .object({
          state_code: z.string(),
          lead_count: z.number(),
        })
        .passthrough(),
    ),
    user_growth: z.array(
      z
        .object({
          month: z.string(),
          new_users: z.number(),
        })
        .passthrough(),
    ),
  })
  .passthrough();

const adminUserListItemSchema = z
  .object({
    id: z.number(),
    name: z.string(),
    email: z.string(),
    role: z.string(),
    is_active: z.boolean(),
    created_at: z.string(),
    license_count: z.number(),
    current_credits: z.number(),
    total_purchases: z.number(),
  })
  .passthrough();

const paginatedUsersSchema: z.ZodType<PaginatedUsers> = z
  .object({
    items: z.array(adminUserListItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  })
  .passthrough();

const adminOrderListItemSchema = z
  .object({
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
  })
  .passthrough();

const paginatedOrdersSchema: z.ZodType<PaginatedOrders> = z
  .object({
    items: z.array(adminOrderListItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  })
  .passthrough();

const adminLeadInventoryItemSchema = z
  .object({
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
  })
  .passthrough();

const paginatedLeadInventorySchema: z.ZodType<PaginatedLeadInventory> = z
  .object({
    items: z.array(adminLeadInventoryItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  })
  .passthrough();

const licenseStatusSummarySchema: z.ZodType<LicenseStatusSummaryItem[]> = z.array(
  z
    .object({
      status: z.enum(["pending", "verified", "rejected"]),
      count: z.number(),
    })
    .passthrough(),
);

const auditLogSchema = z
  .object({
    id: z.number(),
    actor_user_id: z.number().nullable(),
    action: z.string(),
    entity_type: z.string(),
    entity_id: z.number().nullable(),
    meta_data: z.record(z.string(), z.unknown()).nullable(),
    ip_address: z.string().nullable(),
    created_at: z.string(),
  })
  .passthrough();

const userLicenseItemSchema = z
  .object({
    id: z.number(),
    state: z.string(),
    license_number: z.string(),
    license_type: z.string().nullable(),
    verification_status: z.enum(["pending", "verified", "rejected"]),
    created_at: z.string(),
    verified_at: z.string().nullable(),
    rejection_reason: z.string().nullable(),
  })
  .passthrough();

const userCreditSummarySchema = z
  .object({
    total_credits: z.number(),
    remaining_credits: z.number(),
    completed_purchases: z.number(),
  })
  .passthrough();

const userPurchaseItemSchema = z
  .object({
    id: z.number(),
    order_reference: z.string(),
    status: z.string(),
    package_name: z.string().nullable(),
    amount_cents: z.number(),
    currency: z.string(),
    credits_total: z.number(),
    credits_remaining: z.number(),
    purchased_at: z.string(),
  })
  .passthrough();

const userDownloadHistoryItemSchema = z
  .object({
    lead_id: z.number(),
    state_code: z.string(),
    downloaded_at: z.string(),
    csv_batch_id: z.string().nullable(),
  })
  .passthrough();

const userDetailsSchema: z.ZodType<UserDetails> = z
  .object({
    id: z.number(),
    name: z.string(),
    email: z.string(),
    role: z.string(),
    is_active: z.boolean(),
    created_at: z.string(),
    deactivated_at: z.string().nullable(),
    deactivated_by: z.number().nullable(),
    licenses: z.array(z.union([userLicenseItemSchema, licenseSchema])),
    credit_summary: userCreditSummarySchema,
    purchase_history: z.array(userPurchaseItemSchema),
    download_history: z.array(userDownloadHistoryItemSchema),
    recent_activity: z.array(auditLogSchema),
  })
  .passthrough();

const paginatedAuditLogsSchema: z.ZodType<PaginatedAuditLogs> = z
  .object({
    items: z.array(auditLogSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  })
  .passthrough();

const importStatsSchema: z.ZodType<ImportStats> = z
  .object({
    scanned: z.number(),
    inserted: z.number(),
    skipped_duplicates: z.number(),
    failed: z.number(),
    errors: z.array(
      z
        .object({
          row: z.number().optional(),
          error: z.string(),
        })
        .passthrough(),
    ),
  })
  .passthrough();

const leadBulkImportResultSchema: z.ZodType<LeadBulkImportResult> = z
  .object({
    success: z.number(),
    failed: z.number(),
    errors: z.array(
      z
        .object({
          row: z.number(),
          error: z.string(),
        })
        .passthrough(),
    ),
  })
  .passthrough();

const leadBulkImportSchemaSchema: z.ZodType<LeadBulkImportSchema> = z
  .object({
    headers: z.array(z.string()),
    required_values: z.array(z.string()),
    system_fields: z
      .object({
        source: z.string(),
      })
      .passthrough(),
  })
  .passthrough();

const deactivateAdminUserResponseSchema = z
  .object({
    detail: z.string(),
  })
  .passthrough();

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await apiClient.get<DashboardStats>("/admin/dashboard");
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

export const getAnalyticsOverview = async (): Promise<AdminAnalyticsOverview> => {
  const response = await apiClient.get<AdminAnalyticsOverview>("/admin/analytics");
  return parseApiContract(
    adminAnalyticsOverviewSchema,
    response.data,
    "/admin/analytics",
  );
};

export const getUsers = async (
  page: number,
  size: number,
  filters?: UserListFilters,
): Promise<PaginatedUsers> => {
  const params = normalizeParams({
    page,
    size,
    search: filters?.search,
    role: filters?.role,
    status: filters?.status,
  });

  const response = await apiClient.get<PaginatedUsers>("/admin/users", {
    params,
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
): Promise<PaginatedOrders> => {
  const params = normalizeParams({
    page,
    size,
    status,
  });

  const response = await apiClient.get<PaginatedOrders>("/admin/orders", {
    params,
  });
  return parseApiContract(
    paginatedOrdersSchema,
    response.data,
    "/admin/orders",
  );
};

export const getLeadInventory = async (
  page: number,
  size: number,
  filters: LeadInventoryFilters = {},
): Promise<PaginatedLeadInventory> => {
  const params = normalizeParams({
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
  });
  return parseApiContract(
    paginatedLeadInventorySchema,
    response.data,
    "/admin/lead-inventory",
  );
};

export const getLicenseStatusSummary = async (): Promise<LicenseStatusSummaryItem[]> => {
  const response = await apiClient.get<LicenseStatusSummaryItem[]>(
    "/admin/license-status-summary",
  );
  return parseApiContract(
    licenseStatusSummarySchema,
    response.data,
    "/admin/license-status-summary",
  );
};

export const createLeadAsAdmin = async (
  payload: AdminLeadCreatePayload,
): Promise<Lead> => {
  const requestPayload = normalizeParams({
    state_code: payload.state_code.trim().toUpperCase(),
    mobile_phone: payload.mobile_phone,
    first_name: payload.first_name,
    last_name: payload.last_name,
    source: payload.source ?? "manual_entry",
  });

  const response = await apiClient.post<Lead>("/leads/", requestPayload);
  return parseApiContract(leadSchema, response.data, "/leads/");
};

export const getUser = async (userId: number): Promise<UserDetails> => {
  const response = await apiClient.get<UserDetails>(`/admin/users/${userId}`);
  return parseApiContract(
    userDetailsSchema,
    response.data,
    `/admin/users/${userId}`,
  );
};

export const deactivateUser = async (
  userId: number,
  reason?: string,
): Promise<void> => {
  const payload = normalizeParams({ reason }) as DeactivateUserRequest;

  await apiClient.post(`/admin/users/${userId}/deactivate`, payload);
};

export const syncWordPress = async (): Promise<ImportStats> => {
  const response = await apiClient.post<ImportStats>("/admin/sync/wordpress");
  return parseApiContract(
    importStatsSchema,
    response.data,
    "/admin/sync/wordpress",
  );
};

export const getAuditLogs = async (
  filters: AuditLogFilters,
  page: number,
  size: number,
): Promise<PaginatedAuditLogs> => {
  const params = normalizeParams({
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
  const normalizedPayload = normalizeParams({
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
