import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import { licenseSchema } from "@/api/license-contract";
import type { License } from "@/types/license";
import { z } from "zod";

const licenseListSchema: z.ZodType<License[]> = z.array(licenseSchema);

interface RequestOptions {
  signal?: AbortSignal;
}

export const submitLicense = async (data: FormData): Promise<License> => {
  const response = await apiClient.post<License>("/licenses", data, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return parseApiContract(licenseSchema, response.data, "/licenses");
};

export const getMyLicenses = async (
  options: RequestOptions = {},
): Promise<License[]> => {
  const response = await apiClient.get<License[]>("/licenses", {
    signal: options.signal,
  });
  return parseApiContract(licenseListSchema, response.data, "/licenses");
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

  return parseApiContract(
    licenseSchema,
    response.data,
    `/licenses/${licenseId}/resubmit`,
  );
};
