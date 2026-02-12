import apiClient from "@/api/client";
import type {
  LeadDashboardSummary,
  LeadFilters,
  LeadOutcome,
  LeadOutcomeUpdatePayload,
  PaginatedLeads,
} from "@/types/lead";

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

  return response.data;
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
  return response.data;
};

export const getLeadDashboardSummary =
  async (): Promise<LeadDashboardSummary> => {
    const response = await apiClient.get<LeadDashboardSummary>(
      "/leads/dashboard/summary",
    );
    return response.data;
  };
