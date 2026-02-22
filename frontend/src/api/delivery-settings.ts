import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import { z } from "zod";

export interface DeliverySettingsResponse {
  email_alerts_enabled: boolean;
  sms_alerts_enabled: boolean;
  version: number;
  updated_at: string;
  warnings: string[];
}

export interface DeliverySettingsUpdatePayload {
  email_alerts_enabled?: boolean;
  sms_alerts_enabled?: boolean;
  expected_version?: number;
}

const deliverySettingsResponseSchema: z.ZodType<DeliverySettingsResponse> = z
  .looseObject({
    email_alerts_enabled: z.boolean(),
    sms_alerts_enabled: z.boolean(),
    version: z.number(),
    updated_at: z.string(),
    warnings: z.array(z.string()),
  });

export const getMyDeliverySettings =
  async (): Promise<DeliverySettingsResponse> => {
    const response = await apiClient.get<DeliverySettingsResponse>(
      "/delivery-settings/me",
    );
    return parseApiContract(
      deliverySettingsResponseSchema,
      response.data,
      "/delivery-settings/me",
    );
  };

export const updateMyDeliverySettings = async (
  payload: DeliverySettingsUpdatePayload,
): Promise<DeliverySettingsResponse> => {
  const response = await apiClient.patch<DeliverySettingsResponse>(
    "/delivery-settings/me",
    payload,
  );
  return parseApiContract(
    deliverySettingsResponseSchema,
    response.data,
    "/delivery-settings/me",
  );
};
