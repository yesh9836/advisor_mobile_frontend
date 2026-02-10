import axios from "axios";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { createCheckout, getPlans } from "@/api/subscriptions";
import type { SubscriptionPlan } from "@/types/subscription";

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

interface DisplayPlan {
  key: string;
  title: string;
  subtitle: string;
  priceLabel: string;
  leadLine: string;
  features: string[];
  planId: number | null;
}

const formatMoney = (value: number, currency: string): string => {
  return (value / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    maximumFractionDigits: 0,
  });
};

const normalizeFeatures = (features: SubscriptionPlan["features"]): string[] => {
  if (Array.isArray(features)) {
    return features.map((item) => String(item));
  }
  if (features && typeof features === "object") {
    return Object.entries(features).map(([key, value]) => `${key}: ${String(value)}`);
  }
  return [];
};

const toDisplayPlan = (plan: SubscriptionPlan): DisplayPlan => {
  const stateLabel = plan.state_limit === null ? "Unlimited states" : `${plan.state_limit} states`;
  const leadsLabel =
    plan.daily_download_limit >= 999999
      ? "Unlimited daily leads"
      : `${plan.daily_download_limit} daily leads`;

  return {
    key: `plan-${plan.id}`,
    title: plan.name || "Plan",
    subtitle: stateLabel,
    priceLabel: formatMoney(plan.price_cents ?? 0, plan.currency ?? "USD"),
    leadLine: `${leadsLabel} • instant inbox delivery`,
    features: normalizeFeatures(plan.features),
    planId: plan.id,
  };
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item.msg ?? "Validation error").join(", ");
    }
    return error.message || fallback;
  }

  if (error instanceof Error) return error.message;
  return fallback;
};

const SubscriptionPage = () => {
  const [plans, setPlans] = useState<DisplayPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutKey, setCheckoutKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchParams] = useSearchParams();

  const checkoutState = searchParams.get("checkout");
  const checkoutSessionId = searchParams.get("session_id");
  const checkoutNotice =
    checkoutState === "success"
      ? `Checkout completed. Subscription activation is in progress${checkoutSessionId ? ` (session ${checkoutSessionId})` : ""}.`
      : checkoutState === "cancel"
        ? "Checkout canceled. No charge was made."
        : null;

  useEffect(() => {
    let mounted = true;

    const loadPlans = async () => {
      setLoading(true);
      setError(null);
      try {
        const plansData = await getPlans();
        if (!mounted) return;

        setPlans(plansData.map(toDisplayPlan));
      } catch (loadError) {
        if (mounted) {
          setPlans([]);
          setError(getErrorMessage(loadError, "Unable to load plans."));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void loadPlans();

    return () => {
      mounted = false;
    };
  }, []);

  const handleCheckout = async (entry: DisplayPlan) => {
    if (!entry.planId) {
      setError("Checkout is not configured for this preview package yet.");
      return;
    }

    setCheckoutKey(entry.key);
    setError(null);

    try {
      const session = await createCheckout(entry.planId);
      window.location.assign(session.url);
    } catch (checkoutError) {
      setError(getErrorMessage(checkoutError, "Unable to start checkout."));
    } finally {
      setCheckoutKey(null);
    }
  };

  return (
    <div className="page">
      <div>
        <h1>Buy Leads</h1>
        <p className="page-subtitle">Choose a package. Checkout is powered by Stripe.</p>
      </div>

      {checkoutNotice && (
        <div className={checkoutState === "success" ? "success" : "alert"}>
          {checkoutNotice}
        </div>
      )}

      {error && <div className="alert">{error}</div>}

      <section className="grid-3">
        {loading ? (
          <article className="panel">
            <div className="metric-note">Loading plans...</div>
          </article>
        ) : plans.length === 0 ? (
          <article className="panel stack">
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>No Plans Available</h2>
            <p style={{ margin: 0, color: "#475569" }}>
              Plan values from DB are unavailable. Showing 0 until plans are configured.
            </p>
            <div className="panel" style={{ background: "#fafcff" }}>
              <div className="metric-value" style={{ fontSize: 38, marginTop: 0 }}>$0</div>
              <div style={{ color: "#475569" }}>0 daily leads • instant inbox delivery</div>
            </div>
          </article>
        ) : (
          plans.map((entry) => (
          <article key={entry.key} className="panel stack">
            <div className="page-header-row" style={{ alignItems: "flex-start" }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>{entry.title}</h2>
                <p style={{ margin: "4px 0 0 0", color: "#475569" }}>{entry.subtitle}</p>
              </div>
              <span className="badge" style={{ background: "#0b1b49", color: "#fff", borderColor: "#0b1b49" }}>Plan</span>
            </div>

            <div className="panel" style={{ background: "#fafcff" }}>
              <div className="metric-value" style={{ fontSize: 38, marginTop: 0 }}>{entry.priceLabel}</div>
              <div style={{ color: "#475569" }}>{entry.leadLine}</div>
            </div>

            {entry.features.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
                {entry.features.map((feature) => (
                  <li key={feature} style={{ marginBottom: 6 }}>{feature}</li>
                ))}
              </ul>
            )}

            <button type="button" className="btn btn-primary" onClick={() => void handleCheckout(entry)} disabled={checkoutKey === entry.key}>
              {checkoutKey === entry.key ? "Opening Checkout..." : "Checkout (Preview)"}
            </button>

            <button type="button" className="btn btn-secondary">View Details</button>
          </article>
          ))
        )}
      </section>

      <section className="panel page-header-row" style={{ alignItems: "center" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 24, color: "#0b1b49" }}>Add-on Offer</h3>
          <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
            Add-on pricing will populate automatically when configured in backend.
          </p>
        </div>
        <button type="button" className="btn btn-primary">Add Offer</button>
      </section>
    </div>
  );
};

export default SubscriptionPage;
