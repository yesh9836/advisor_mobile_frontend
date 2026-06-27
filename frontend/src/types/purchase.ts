export interface PurchasePackage {
  id: number;
  name: string;
  price_cents: number;
  currency: string;
  state_limit: number | null;
  daily_download_limit: number;
  credits_total?: number;
  features: string[] | Record<string, unknown> | null;
  stripe_price_id: string;
  created_at: string;
}

export interface PurchaseCheckoutSession {
  session_id: string;
  url: string;
}

export interface PurchaseBalance {
  total_credits: number;
  remaining_credits: number;
  completed_purchases: number;
}

export interface PurchaseOrderItem {
  id: number;
  order_reference: string;
  package_name: string | null;
  amount_cents: number;
  currency: string;
  credits_total: number;
  entitled_credits_total: number;
  credits_remaining: number;
  status: string;
  assigned_count: number;
  unfulfilled_count: number;
  fulfillment_status:
    | "fulfilled"
    | "partially_fulfilled"
    | "pending_inventory"
    | "pending"
    | "not_completed";
  purchased_at: string;
  stripe_checkout_session_id: string;
  stripe_payment_intent_id: string | null;
}

export interface PaginatedPurchaseOrders {
  items: PurchaseOrderItem[];
  total: number;
  page: number;
  size: number;
}

export interface PurchaseHistory {
  items: PurchaseOrderItem[];
}

export interface FirstPurchaseAddonOfferUpdatePayload {
  is_enabled: boolean;
  trigger_package_id: number | null;
  offer_credits_total: number | null;
  offer_price_cents: number | null;
  offer_currency: string | null;
  headline: string | null;
  message: string | null;
  cta_label: string | null;
  starts_at: string | null;
  ends_at: string | null;
}

export interface FirstPurchaseAddonOfferConfig {
  id: number | null;
  is_enabled: boolean;
  trigger_package_id: number | null;
  trigger_package_name: string | null;
  offer_package_id: number | null;
  offer_package_name: string | null;
  offer_price_cents: number | null;
  offer_currency: string | null;
  offer_credits_total: number | null;
  headline: string | null;
  message: string | null;
  cta_label: string | null;
  starts_at: string | null;
  ends_at: string | null;
  updated_at: string | null;
  updated_by: number | null;
  inventory_ready?: boolean | null;
  inventory_available_count?: number | null;
  inventory_required_count?: number | null;
  inventory_gate_code?: string | null;
  inventory_gate_message?: string | null;
}

export interface FirstPurchaseAddonOfferAdvisor {
  trigger_package_id: number;
  offer_package_id: number;
  offer_package_name: string;
  offer_price_cents: number;
  offer_currency: string;
  offer_credits_total: number;
  headline: string;
  message: string;
  cta_label: string;
}

export interface FirstPurchaseAddonOfferEligibility {
  eligible: boolean;
  offer: FirstPurchaseAddonOfferAdvisor | null;
  rejection_code?: string | null;
  rejection_message?: string | null;
  inventory_available_count?: number | null;
  inventory_required_count?: number | null;
}
