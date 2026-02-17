import apiClient from "@/api/client";

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

export const getMyDeliverySettings =
  async (): Promise<DeliverySettingsResponse> => {
    const response = await apiClient.get<DeliverySettingsResponse>(
      "/delivery-settings/me",
    );
    return response.data;
  };

export const updateMyDeliverySettings = async (
  payload: DeliverySettingsUpdatePayload,
): Promise<DeliverySettingsResponse> => {
  const response = await apiClient.patch<DeliverySettingsResponse>(
    "/delivery-settings/me",
    payload,
  );
  return response.data;
};
