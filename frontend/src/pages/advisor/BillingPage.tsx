import { useEffect, useState } from "react";

import { getBillingSummary } from "@/api/subscriptions";
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

const BillingPage = () => {
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const summary = await getBillingSummary();
        setBilling(summary);
      } catch (loadError) {
        setBilling(null);
        setError(getApiErrorMessage(loadError, "Unable to load billing data."));
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

  const method = billing?.payment_method;
  const invoices = billing?.invoices ?? [];

  return (
    <div className="page">
      <div>
        <h1>Billing</h1>
        <p className="page-subtitle">
          Invoices, payment methods, and purchase history.
        </p>
      </div>

      {error && <div className="alert">{error}</div>}
      {message && <div className="success">{message}</div>}

      <section className="grid-main">
        <article className="panel stack">
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
                    {formatAmount(invoice.amount_paid_cents, invoice.currency)}
                  </p>
                  <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                    {formatDate(invoice.created_at)} • {invoice.status}
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
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
              Payment Method
            </h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Card on file for instant lead fulfillment.
            </p>
          </div>

          {loading ? (
            <div className="metric-note">Loading payment method...</div>
          ) : !method ? (
            <div className="metric-note">No payment method available.</div>
          ) : (
            <div className="panel" style={{ background: "#fafcff" }}>
              <p
                style={{
                  margin: 0,
                  fontSize: 24,
                  fontWeight: 800,
                  color: "#0b1b49",
                }}
              >
                {method.brand.toUpperCase()} •••• {method.last4}
              </p>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Expires {String(method.exp_month).padStart(2, "0")}/
                {method.exp_year}
              </p>
              {method.is_placeholder && (
                <p
                  style={{
                    margin: "8px 0 0 0",
                    color: "#475569",
                    fontSize: 13,
                  }}
                >
                  Placeholder data shown until Stripe payment details are
                  available.
                </p>
              )}
            </div>
          )}

          <button type="button" className="btn btn-primary" disabled>
            Update Card (Stripe Hosted)
          </button>
        </aside>
      </section>
    </div>
  );
};

export default BillingPage;
