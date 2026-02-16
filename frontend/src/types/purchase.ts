export interface PurchasePackage {
  id: number;
  name: string;
  price_cents: number;
  currency: string;
  state_limit: number | null;
  daily_download_limit: number;
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
  credits_remaining: number;
  status: string;
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
