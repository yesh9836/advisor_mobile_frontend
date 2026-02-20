import apiClient from "@/api/client";
import type { BillingSummary } from "@/types/subscription";
import type {
  FirstPurchaseAddonOfferEligibility,
  PaginatedPurchaseOrders,
  PurchaseBalance,
  PurchaseCheckoutSession,
  PurchaseHistory,
  PurchasePackage,
} from "@/types/purchase";

export const getPackages = async (): Promise<PurchasePackage[]> => {
  const response = await apiClient.get<PurchasePackage[]>("/purchases/packages");
  return response.data;
};

export const createCheckout = async (
  packageId: number,
  retryToken?: string,
): Promise<PurchaseCheckoutSession> => {
  const response = await apiClient.post<PurchaseCheckoutSession>(
    "/purchases/checkout",
    {
      package_id: packageId,
      ...(retryToken ? { retry_token: retryToken } : {}),
    },
  );
  return response.data;
};

export const getPurchaseBalance = async (): Promise<PurchaseBalance> => {
  const response = await apiClient.get<PurchaseBalance>("/purchases/balance");
  return response.data;
};

export const getPurchaseHistory = async (limit = 50): Promise<PurchaseHistory> => {
  const response = await apiClient.get<PurchaseHistory>("/purchases/history", {
    params: { limit },
  });
  return response.data;
};

export const getPurchaseBillingSummary = async (): Promise<BillingSummary> => {
  const response = await apiClient.get<BillingSummary>("/purchases/billing/summary");
  return response.data;
};

export const getPurchaseOrders = async (
  page: number,
  size: number,
  status?: string,
): Promise<PaginatedPurchaseOrders> => {
  const params: Record<string, string | number> = { page, size };
  if (status && status.trim()) {
    params.status = status.trim();
  }
  const response = await apiClient.get<PaginatedPurchaseOrders>("/purchases/orders", {
    params,
  });
  return response.data;
};

export const getFirstPurchaseOfferEligibility = async (
  checkoutSessionId: string,
): Promise<FirstPurchaseAddonOfferEligibility> => {
  const response = await apiClient.get<FirstPurchaseAddonOfferEligibility>(
    "/purchases/first-purchase-offer",
    {
      params: {
        checkout_session_id: checkoutSessionId,
      },
    },
  );
  return response.data;
};
