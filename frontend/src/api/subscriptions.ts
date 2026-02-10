import apiClient from "@/api/client";
import type {
  BillingSummary,
  CheckoutSession,
  Subscription,
  SubscriptionPlan,
} from "@/types/subscription";

export const getPlans = async (): Promise<SubscriptionPlan[]> => {
  const response = await apiClient.get<SubscriptionPlan[]>(
    "/subscriptions/plans",
  );
  return response.data;
};

export const createCheckout = async (
  planId: number,
): Promise<CheckoutSession> => {
  const response = await apiClient.post<CheckoutSession>(
    "/subscriptions/checkout",
    { plan_id: planId },
  );
  return response.data;
};

export const getCurrentSubscription = async (): Promise<Subscription> => {
  const response = await apiClient.get<Subscription>("/subscriptions/current");
  return response.data;
};

export const getBillingSummary = async (): Promise<BillingSummary> => {
  const response = await apiClient.get<BillingSummary>(
    "/subscriptions/billing/summary",
  );
  return response.data;
};

export const cancelSubscription = async (): Promise<Subscription> => {
  const response = await apiClient.post<Subscription>("/subscriptions/cancel");
  return response.data;
};
