import apiClient from "@/api/client";
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

export const getPendingLicenses = async (): Promise<LicenseWithUser[]> => {
  const response = await apiClient.get<LicenseWithUser[]>("/licenses/pending");
  return response.data;
};

export const getProcessedLicenses = async (): Promise<AdminLicenseDecisionRow[]> => {
  const response = await apiClient.get<AdminLicenseDecisionRow[]>(
    "/licenses/processed",
  );
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
