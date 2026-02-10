import apiClient from "@/api/client";
import type { License } from "@/types/license";

export const submitLicense = async (data: FormData): Promise<License> => {
  const response = await apiClient.post<License>("/licenses", data, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export const getMyLicenses = async (): Promise<License[]> => {
  const response = await apiClient.get<License[]>("/licenses");
  return response.data;
};

export const resubmitLicense = async (
  licenseId: number,
  data: FormData,
): Promise<License> => {
  const response = await apiClient.post<License>(
    `/licenses/${licenseId}/resubmit`,
    data,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );

  return response.data;
};
