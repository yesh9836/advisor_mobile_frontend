import apiClient from "@/api/client";
import { parseApiContract } from "@/api/contract";
import type { BillingSummary } from "@/types/subscription";
import type {
  FirstPurchaseAddonOfferAdvisor,
  FirstPurchaseAddonOfferEligibility,
  PaginatedPurchaseOrders,
  PurchaseOrderItem,
  PurchaseBalance,
  PurchaseCheckoutSession,
  PurchaseHistory,
  PurchasePackage,
} from "@/types/purchase";
import { z } from "zod";

const featuresSchema = z.union([
  z.array(z.string()),
  z.record(z.string(), z.unknown()),
  z.null(),
]);

const purchasePackageSchema: z.ZodType<PurchasePackage> = z
  .looseObject({
    id: z.number(),
    name: z.string(),
    price_cents: z.number(),
    currency: z.string(),
    state_limit: z.number().nullable(),
    daily_download_limit: z.number(),
    features: featuresSchema,
    stripe_price_id: z.string(),
    created_at: z.string(),
  });

const purchaseCheckoutSchema: z.ZodType<PurchaseCheckoutSession> = z
  .looseObject({
    session_id: z.string(),
    url: z.string(),
  });

const purchaseBalanceSchema: z.ZodType<PurchaseBalance> = z
  .looseObject({
    total_credits: z.number(),
    remaining_credits: z.number(),
    completed_purchases: z.number(),
  });

const purchaseOrderItemSchema: z.ZodType<PurchaseOrderItem> = z
  .looseObject({
    id: z.number(),
    order_reference: z.string(),
    package_name: z.string().nullable(),
    amount_cents: z.number(),
    currency: z.string(),
    credits_total: z.number(),
    entitled_credits_total: z.number(),
    credits_remaining: z.number(),
    status: z.string(),
    assigned_count: z.number(),
    unfulfilled_count: z.number(),
    fulfillment_status: z.enum([
      "fulfilled",
      "partially_fulfilled",
      "pending_inventory",
      "pending",
      "not_completed",
    ]),
    purchased_at: z.string(),
    stripe_checkout_session_id: z.string(),
    stripe_payment_intent_id: z.string().nullable(),
  });

const paginatedPurchaseOrdersSchema: z.ZodType<PaginatedPurchaseOrders> = z
  .looseObject({
    items: z.array(purchaseOrderItemSchema),
    total: z.number(),
    page: z.number(),
    size: z.number(),
  });

const purchaseHistorySchema: z.ZodType<PurchaseHistory> = z
  .looseObject({
    items: z.array(purchaseOrderItemSchema),
  });

const billingSummarySchema: z.ZodType<BillingSummary> = z
  .looseObject({
    payment_method: z
      .looseObject({
        brand: z.string(),
        last4: z.string(),
        exp_month: z.number(),
        exp_year: z.number(),
        funding: z.string().nullable(),
        country: z.string().nullable(),
        is_placeholder: z.boolean(),
      })
      .nullable(),
    invoices: z.array(
      z
        .looseObject({
          stripe_invoice_id: z.string(),
          amount_paid_cents: z.number(),
          currency: z.string(),
          status: z.string(),
          created_at: z.string(),
          package_name: z.string().nullable(),
          hosted_invoice_url: z.string().nullable(),
          invoice_pdf: z.string().nullable(),
          description: z.string().nullable(),
        }),
    ),
  });

const firstPurchaseOfferSchema: z.ZodType<FirstPurchaseAddonOfferAdvisor> = z
  .looseObject({
    trigger_package_id: z.number(),
    offer_package_id: z.number(),
    offer_package_name: z.string(),
    offer_price_cents: z.number(),
    offer_currency: z.string(),
    offer_credits_total: z.number(),
    headline: z.string(),
    message: z.string(),
    cta_label: z.string(),
  });

const firstPurchaseOfferEligibilitySchema: z.ZodType<FirstPurchaseAddonOfferEligibility> =
  z
    .looseObject({
      eligible: z.boolean(),
      offer: firstPurchaseOfferSchema.nullable(),
      rejection_code: z.string().nullable().optional(),
      rejection_message: z.string().nullable().optional(),
      inventory_available_count: z.number().nullable().optional(),
      inventory_required_count: z.number().nullable().optional(),
    });

export const getPackages = async (): Promise<PurchasePackage[]> => {
  const response = await apiClient.get<PurchasePackage[]>("/purchases/packages");
  return parseApiContract(
    z.array(purchasePackageSchema),
    response.data,
    "/purchases/packages",
  );
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
  return parseApiContract(
    purchaseCheckoutSchema,
    response.data,
    "/purchases/checkout",
  );
};

export const getPurchaseBalance = async (): Promise<PurchaseBalance> => {
  const response = await apiClient.get<PurchaseBalance>("/purchases/balance");
  return parseApiContract(
    purchaseBalanceSchema,
    response.data,
    "/purchases/balance",
  );
};

export const getPurchaseHistory = async (limit = 50): Promise<PurchaseHistory> => {
  const response = await apiClient.get<PurchaseHistory>("/purchases/history", {
    params: { limit },
  });
  return parseApiContract(
    purchaseHistorySchema,
    response.data,
    "/purchases/history",
  );
};

export const getPurchaseBillingSummary = async (): Promise<BillingSummary> => {
  const response = await apiClient.get<BillingSummary>("/purchases/billing/summary");
  return parseApiContract(
    billingSummarySchema,
    response.data,
    "/purchases/billing/summary",
  );
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
  return parseApiContract(
    paginatedPurchaseOrdersSchema,
    response.data,
    "/purchases/orders",
  );
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
  return parseApiContract(
    firstPurchaseOfferEligibilitySchema,
    response.data,
    "/purchases/first-purchase-offer",
  );
};
