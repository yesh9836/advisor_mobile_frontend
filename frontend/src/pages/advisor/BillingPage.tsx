import { useEffect, useState } from "react";
import axios from "axios";

import { getPurchaseBillingSummary, getPurchaseHistory } from "@/api/purchases";
import type { PurchaseOrderItem } from "@/types/purchase";
import type { BillingInvoice, BillingSummary } from "@/types/subscription";
import { getApiErrorMessage } from "@/utils/api-error";

const formatDate = (value: string): string => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const formatAmount = (amountCents: number, currency: string): string => {
  return (amountCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
  });
};

const toFallbackInvoice = (purchase: PurchaseOrderItem): BillingInvoice => {
  return {
    stripe_invoice_id:
      purchase.stripe_payment_intent_id
      || purchase.order_reference
      || `purchase-${purchase.id}`,
    amount_paid_cents: purchase.amount_cents,
    currency: purchase.currency,
    status: purchase.status,
    created_at: purchase.purchased_at,
    package_name: purchase.package_name,
    hosted_invoice_url: null,
    invoice_pdf: null,
    description: null,
  };
};

const isLegacySummaryOutage = (error: unknown): boolean =>
  axios.isAxiosError(error) && error.response?.status === 502;

const BillingPage = () => {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statusNote, setStatusNote] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      setStatusNote(null);

      try {
        const summary = await getPurchaseBillingSummary();
        setBilling(summary);
        if (summary.provider_status === "degraded") {
          setStatusNote("Stripe billing details are temporarily unavailable. Showing purchase history.");
        }
      } catch (summaryError) {
        try {
          const history = await getPurchaseHistory();
          const fallbackInvoices = history.items
            .map(toFallbackInvoice)
            .sort((a, b) => {
              const aTime = new Date(a.created_at).getTime();
              const bTime = new Date(b.created_at).getTime();
              return (Number.isNaN(bTime) ? 0 : bTime) - (Number.isNaN(aTime) ? 0 : aTime);
            });
          setBilling({
            payment_method: null,
            invoices: fallbackInvoices,
            provider_status: "degraded",
            degradation_reason: "billing_summary_unavailable",
          });
          setStatusNote(
            isLegacySummaryOutage(summaryError)
              ? "Stripe billing details are temporarily unavailable. Showing purchase history."
              : "Billing summary is temporarily unavailable. Showing purchase history.",
          );
        } catch (historyError) {
          setBilling(null);
          setError(getApiErrorMessage(historyError, getApiErrorMessage(summaryError, "Unable to load billing data.")));
        }
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const handleDownload = (invoice: BillingInvoice) => {
    const url = invoice.invoice_pdf || invoice.hosted_invoice_url;
    if (!url) {
      setMessage("Invoice link not available yet.");
      window.setTimeout(() => setMessage(null), 2200);
      return;
    }

    window.open(url, "_blank", "noopener,noreferrer");
  };

  const invoices = billing?.invoices ?? [];

  return (
    <div className="page">
      <div>
        <h1>Billing</h1>
        <p className="page-subtitle">
          Invoices and purchase history.
        </p>
      </div>

      {error && <div className="alert">{error}</div>}
      {statusNote && <div className="metric-note">{statusNote}</div>}
      {message && <div className="success">{message}</div>}

      <section className="panel stack">
        <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
          Recent Purchases
        </h2>

        {loading ? (
          <div className="metric-note">Loading purchases...</div>
        ) : invoices.length === 0 ? (
          <div className="metric-note">No invoices yet.</div>
        ) : (
          invoices.map((invoice) => (
            <div
              key={invoice.stripe_invoice_id}
              className="panel page-header-row"
              style={{ alignItems: "center", padding: 12 }}
            >
              <div>
                <p
                  style={{
                    margin: 0,
                    fontSize: 18,
                    fontWeight: 700,
                    color: "#0b1b49",
                  }}
                >
                  {invoice.package_name?.trim()
                    || formatAmount(invoice.amount_paid_cents, invoice.currency)}
                </p>
                <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                  {formatDate(invoice.created_at)} •{" "}
                  {invoice.invoice_pdf || invoice.hosted_invoice_url
                    ? "Stripe receipt available"
                    : "Stripe receipt pending"}
                </p>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => handleDownload(invoice)}
              >
                Download Invoice
              </button>
            </div>
          ))
        )}
      </section>
    </div>
  );
};

export default BillingPage;
