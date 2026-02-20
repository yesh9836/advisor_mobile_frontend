export type SubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "unpaid"
  | "incomplete"
  | "incomplete_expired"
  | "paused"
  | (string & {});

export interface SubscriptionPlan {
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

export interface Subscription {
  id: number;
  user_id: number;
  plan_id: number;
  stripe_subscription_id: string;
  status: SubscriptionStatus;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
  plan: SubscriptionPlan;
}

export interface CheckoutSession {
  session_id: string;
  url: string;
}

export interface BillingPaymentMethod {
  brand: string;
  last4: string;
  exp_month: number;
  exp_year: number;
  funding: string | null;
  country: string | null;
  is_placeholder: boolean;
}

export interface BillingInvoice {
  stripe_invoice_id: string;
  amount_paid_cents: number;
  currency: string;
  status: string;
  created_at: string;
  package_name: string | null;
  hosted_invoice_url: string | null;
  invoice_pdf: string | null;
  description: string | null;
}

export interface BillingSummary {
  payment_method: BillingPaymentMethod | null;
  invoices: BillingInvoice[];
}
