import apiClient from "@/api/client";
import type {
  AuditLogFilters,
  DashboardStats,
  DeactivateUserRequest,
  ImportStats,
  LeadBulkImportResult,
  PaginatedAuditLogs,
  PaginatedOrders,
  PaginatedUsers,
  UserDetails,
  UserListFilters,
} from "@/types/admin";
import type {
  AdminLicenseDecisionRow,
  License,
  LicenseWithUser,
} from "@/types/license";

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

export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await apiClient.get<DashboardStats>("/admin/dashboard");
  return response.data;
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
  return response.data;
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
  return response.data;
};

export const getUser = async (userId: number): Promise<UserDetails> => {
  const response = await apiClient.get<UserDetails>(`/admin/users/${userId}`);
  return response.data;
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
  return response.data;
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
  return response.data;
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
  return response.data;
};

export const getPendingLicenses = async (): Promise<LicenseWithUser[]> => {
  const response = await apiClient.get<LicenseWithUser[]>("/licenses/pending");
  return response.data;
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
  return response.data;
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
  return response.data;
};

export const approveLicense = async (licenseId: number): Promise<License> => {
  const response = await apiClient.post<License>(`/licenses/${licenseId}/approve`);
  return response.data;
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
  return response.data;
};

export const downloadLicenseDocument = async (
  licenseId: number,
): Promise<LicenseDocumentDownload> => {
  const response = await apiClient.get<Blob>(`/licenses/${licenseId}/document`, {
    responseType: "blob",
  });

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

  return {
    blob: response.data,
    contentType: (response.headers["content-type"] || "").toLowerCase(),
  };
};
