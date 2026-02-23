import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { getMyLicenses } from "@/api/licenses";
import {
  createCheckout,
  getFirstPurchaseOfferEligibility,
  getPackages,
  getPurchaseHistory,
} from "@/api/purchases";
import type {
  FirstPurchaseAddonOfferAdvisor,
  PurchaseOrderItem,
  PurchasePackage,
} from "@/types/purchase";
import { getApiErrorMessage } from "@/utils/api-error";

interface DisplayPlan {
  key: string;
  title: string;
  subtitle: string;
  priceLabel: string;
  leadLine: string;
  features: string[];
  packageId: number | null;
}

const formatMoney = (value: number, currency: string): string => {
  return (value / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    maximumFractionDigits: 0,
  });
};

const normalizeFeatures = (features: PurchasePackage["features"]): string[] => {
  if (Array.isArray(features)) {
    return features.map((item) => String(item));
  }
  if (features && typeof features === "object") {
    return Object.entries(features).map(
      ([key, value]) => `${key}: ${String(value)}`,
    );
  }
  return [];
};

const toDisplayPlan = (packageOption: PurchasePackage): DisplayPlan => {
  const stateLabel =
    packageOption.state_limit === null
      ? "Unlimited states"
      : `${packageOption.state_limit} states`;
  const leadsLabel =
    packageOption.daily_download_limit >= 999999
      ? "Unlimited lead credits"
      : `${packageOption.daily_download_limit} lead credits`;

  return {
    key: `package-${packageOption.id}`,
    title: packageOption.name || "Package",
    subtitle: stateLabel,
    priceLabel: formatMoney(
      packageOption.price_cents ?? 0,
      packageOption.currency ?? "USD",
    ),
    leadLine: `${leadsLabel} • instant inbox delivery`,
    features: normalizeFeatures(packageOption.features),
    packageId: packageOption.id,
  };
};

const buildCheckoutFulfillmentNotice = (
  purchase: PurchaseOrderItem | null,
  checkoutSessionId: string | null,
): string => {
  if (!purchase) {
    return `Checkout completed. Your lead credits are available${checkoutSessionId ? ` (session ${checkoutSessionId})` : ""}.`;
  }

  return `Checkout completed. Delivered now: ${purchase.assigned_count}/${purchase.entitled_credits_total}. Pending auto-delivery: ${Math.max(purchase.unfulfilled_count, 0)}.`;
};

const buildCheckoutRetryToken = (scope: string): string => {
  const uuidEntropy =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "")
      : Math.random().toString(36).slice(2, 14);
  return `retry_${scope}_${Date.now().toString(36)}_${uuidEntropy}`;
};

const CHECKOUT_SYNC_MAX_ATTEMPTS = 6;
const CHECKOUT_SYNC_RETRY_DELAY_MS = 1500;
const CHECKOUT_RETRY_TOKEN_STORAGE_PREFIX = "advisor_checkout_retry_token_v1";
const CHECKOUT_RETRY_TOKEN_TTL_MS = 45 * 60 * 1000;

interface CheckoutRetryTokenRecord {
  token: string;
  expires_at_ms: number;
}

const checkoutRetryTokenStorageKey = (scope: string): string =>
  `${CHECKOUT_RETRY_TOKEN_STORAGE_PREFIX}:${scope}`;

const readPersistedCheckoutRetryToken = (scope: string): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const rawValue = window.sessionStorage.getItem(checkoutRetryTokenStorageKey(scope));
    if (!rawValue) {
      return null;
    }
    const parsed = JSON.parse(rawValue) as CheckoutRetryTokenRecord;
    if (
      typeof parsed?.token !== "string" ||
      !parsed.token.trim() ||
      typeof parsed?.expires_at_ms !== "number"
    ) {
      window.sessionStorage.removeItem(checkoutRetryTokenStorageKey(scope));
      return null;
    }
    if (parsed.expires_at_ms <= Date.now()) {
      window.sessionStorage.removeItem(checkoutRetryTokenStorageKey(scope));
      return null;
    }
    return parsed.token;
  } catch {
    window.sessionStorage.removeItem(checkoutRetryTokenStorageKey(scope));
    return null;
  }
};

const persistCheckoutRetryToken = (scope: string, token: string): void => {
  if (typeof window === "undefined") {
    return;
  }
  const record: CheckoutRetryTokenRecord = {
    token,
    expires_at_ms: Date.now() + CHECKOUT_RETRY_TOKEN_TTL_MS,
  };
  try {
    window.sessionStorage.setItem(
      checkoutRetryTokenStorageKey(scope),
      JSON.stringify(record),
    );
  } catch {
    // Ignore storage write failures so checkout remains functional.
  }
};

const getOrCreateCheckoutRetryToken = (scope: string): string => {
  const existing = readPersistedCheckoutRetryToken(scope);
  if (existing) {
    return existing;
  }
  const token = buildCheckoutRetryToken(scope);
  persistCheckoutRetryToken(scope, token);
  return token;
};

const clearPersistedCheckoutRetryTokens = (): void => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const keysToRemove: string[] = [];
    for (let index = 0; index < window.sessionStorage.length; index += 1) {
      const storageKey = window.sessionStorage.key(index);
      if (storageKey?.startsWith(`${CHECKOUT_RETRY_TOKEN_STORAGE_PREFIX}:`)) {
        keysToRemove.push(storageKey);
      }
    }
    keysToRemove.forEach((storageKey) => window.sessionStorage.removeItem(storageKey));
  } catch {
    // Ignore storage read/remove failures so checkout success flow still renders.
  }
};

const SubscriptionPage = () => {
  const navigate = useNavigate();
  const [plans, setPlans] = useState<DisplayPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [checkoutKey, setCheckoutKey] = useState<string | null>(null);
  const [addOnCheckoutLoading, setAddOnCheckoutLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkoutNotice, setCheckoutNotice] = useState<string | null>(null);
  const [addOnOffer, setAddOnOffer] = useState<FirstPurchaseAddonOfferAdvisor | null>(null);
  const [licenseGateLoading, setLicenseGateLoading] = useState(true);
  const [hasVerifiedLicense, setHasVerifiedLicense] = useState(false);
  const [licenseGateMessage, setLicenseGateMessage] = useState<string | null>(null);
  const [searchParams] = useSearchParams();

  const checkoutState = searchParams.get("checkout");
  const checkoutSessionId = searchParams.get("session_id");
  const checkoutBlocked = licenseGateLoading || !hasVerifiedLicense;

  useEffect(() => {
    let mounted = true;

    const loadLicenseGate = async () => {
      setLicenseGateLoading(true);
      try {
        const licenses = await getMyLicenses();
        if (!mounted) return;

        const verified = licenses.some(
          (license) => license.verification_status === "verified",
        );
        setHasVerifiedLicense(verified);
        if (verified) {
          setLicenseGateMessage(null);
          return;
        }

        const hasPendingLicense = licenses.some(
          (license) => license.verification_status === "pending",
        );
        const hasRejectedLicense = licenses.some(
          (license) => license.verification_status === "rejected",
        );

        if (licenses.length === 0) {
          setLicenseGateMessage(
            "Submit a license from your profile to unlock lead checkout.",
          );
          return;
        }
        if (hasPendingLicense) {
          setLicenseGateMessage(
            "Your license is pending admin review. Checkout unlocks after approval.",
          );
          return;
        }
        if (hasRejectedLicense) {
          setLicenseGateMessage(
            "Your license was rejected. Resubmit from your profile to unlock checkout.",
          );
          return;
        }

        setLicenseGateMessage("A verified license is required before checkout.");
      } catch {
        if (!mounted) return;
        setHasVerifiedLicense(false);
        setLicenseGateMessage(
          "Unable to confirm your license status right now. Open profile to review your licenses.",
        );
      } finally {
        if (mounted) {
          setLicenseGateLoading(false);
        }
      }
    };

    void loadLicenseGate();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    const loadPackages = async () => {
      setLoading(true);
      setError(null);
      try {
        const packages = await getPackages();
        if (!mounted) return;

        setPlans(packages.map(toDisplayPlan));
      } catch (loadError) {
        if (mounted) {
          setPlans([]);
          setError(getApiErrorMessage(loadError, "Unable to load packages."));
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void loadPackages();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    let syncAttempt = 0;
    let retryTimerId: ReturnType<typeof setTimeout> | null = null;

    const loadCheckoutNotice = async () => {
      if (checkoutState === "cancel") {
        setCheckoutNotice("Checkout canceled. No charge was made.");
        setAddOnOffer(null);
        return;
      }
      if (checkoutState !== "success") {
        setCheckoutNotice(null);
        setAddOnOffer(null);
        return;
      }
      clearPersistedCheckoutRetryTokens();

      if (!checkoutSessionId) {
        setCheckoutNotice(buildCheckoutFulfillmentNotice(null, null));
        setAddOnOffer(null);
        return;
      }

      try {
        const history = await getPurchaseHistory(20);
        if (!active) return;
        const matched = history.items.find(
          (item) => item.stripe_checkout_session_id === checkoutSessionId,
        );
        setCheckoutNotice(buildCheckoutFulfillmentNotice(matched ?? null, checkoutSessionId));
        if (!matched) {
          setAddOnOffer(null);
          if (syncAttempt < CHECKOUT_SYNC_MAX_ATTEMPTS - 1) {
            syncAttempt += 1;
            retryTimerId = setTimeout(() => {
              void loadCheckoutNotice();
            }, CHECKOUT_SYNC_RETRY_DELAY_MS);
          }
          return;
        }

        const eligibility = await getFirstPurchaseOfferEligibility(checkoutSessionId);
        if (!active) return;
        if (eligibility.eligible && eligibility.offer) {
          setAddOnOffer(eligibility.offer);
          return;
        }
        setAddOnOffer(null);
      } catch {
        if (!active) return;
        setCheckoutNotice(buildCheckoutFulfillmentNotice(null, checkoutSessionId));
        setAddOnOffer(null);
        if (syncAttempt < CHECKOUT_SYNC_MAX_ATTEMPTS - 1) {
          syncAttempt += 1;
          retryTimerId = setTimeout(() => {
            void loadCheckoutNotice();
          }, CHECKOUT_SYNC_RETRY_DELAY_MS);
        }
      }
    };

    void loadCheckoutNotice();

    return () => {
      active = false;
      if (retryTimerId !== null) {
        clearTimeout(retryTimerId);
      }
    };
  }, [checkoutSessionId, checkoutState]);

  const handleCheckout = async (entry: DisplayPlan) => {
    if (!entry.packageId) {
      setError("Checkout is not configured for this package yet.");
      return;
    }

    setCheckoutKey(entry.key);
    setError(null);
    setAddOnOffer(null);

    try {
      const tokenScope = `pkg${entry.packageId}`;
      const retryToken = getOrCreateCheckoutRetryToken(tokenScope);
      const session = await createCheckout(entry.packageId, retryToken);
      window.location.assign(session.url);
    } catch (checkoutError) {
      setError(getApiErrorMessage(checkoutError, "Unable to start checkout."));
    } finally {
      setCheckoutKey(null);
    }
  };

  const handleAddOnCheckout = async () => {
    if (!addOnOffer) {
      return;
    }

    setAddOnCheckoutLoading(true);
    setError(null);

    try {
      const tokenScope = `offer${addOnOffer.offer_package_id}`;
      const retryToken = getOrCreateCheckoutRetryToken(tokenScope);
      const session = await createCheckout(addOnOffer.offer_package_id, retryToken);
      window.location.assign(session.url);
    } catch (checkoutError) {
      setError(getApiErrorMessage(checkoutError, "Unable to start checkout."));
    } finally {
      setAddOnCheckoutLoading(false);
    }
  };

  return (
    <div className="page">
      {addOnOffer && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="first-purchase-offer-title"
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.45)",
            display: "grid",
            placeItems: "center",
            zIndex: 120,
            padding: 16,
          }}
        >
          <section
            className="panel stack"
            style={{
              width: "min(620px, 100%)",
              maxHeight: "90vh",
              overflowY: "auto",
            }}
          >
            <div>
              <h2 id="first-purchase-offer-title" style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>
                {addOnOffer.headline}
              </h2>
              <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
                {addOnOffer.message}
              </p>
            </div>

            <div className="panel" style={{ background: "#f8fafc" }}>
              <div className="metric-value" style={{ marginTop: 0, fontSize: 34 }}>
                {formatMoney(
                  addOnOffer.offer_price_cents,
                  addOnOffer.offer_currency,
                )}
              </div>
              <div style={{ color: "#475569" }}>
                {addOnOffer.offer_package_name} • {addOnOffer.offer_credits_total} lead credits
              </div>
            </div>

            <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setAddOnOffer(null)}
                disabled={addOnCheckoutLoading}
              >
                No Thanks
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleAddOnCheckout()}
                disabled={addOnCheckoutLoading}
              >
                {addOnCheckoutLoading ? "Opening Checkout..." : addOnOffer.cta_label}
              </button>
            </div>
          </section>
        </div>
      )}

      <div>
        <h1>Buy Leads</h1>
        <p className="page-subtitle">Choose a package.</p>
      </div>

      {licenseGateLoading ? (
        <div className="panel">
          <div className="metric-note">Checking license verification...</div>
        </div>
      ) : !hasVerifiedLicense ? (
        <div className="alert">
          <div>{licenseGateMessage ?? "A verified license is required before checkout."}</div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ marginTop: 12 }}
            onClick={() => navigate("/profile")}
          >
            Open Profile
          </button>
        </div>
      ) : null}

      {checkoutNotice && (
        <div className={checkoutState === "success" ? "success" : "alert"}>
          {checkoutNotice}
        </div>
      )}

      {error && <div className="alert">{error}</div>}

      <section className="grid-3">
        {loading ? (
          <article className="panel">
            <div className="metric-note">Loading packages...</div>
          </article>
        ) : plans.length === 0 ? (
          <article className="panel stack">
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
              No Packages Available
            </h2>
            <p style={{ margin: 0, color: "#475569" }}>
              Package values from DB are unavailable. Showing 0 until packages
              are configured.
            </p>
            <div className="panel" style={{ background: "#fafcff" }}>
              <div
                className="metric-value"
                style={{ fontSize: 38, marginTop: 0 }}
              >
                $0
              </div>
              <div style={{ color: "#475569" }}>
                0 lead credits • instant inbox delivery
              </div>
            </div>
          </article>
        ) : (
          plans.map((entry) => (
            <article key={entry.key} className="panel stack">
              <div
                className="page-header-row"
                style={{ alignItems: "flex-start" }}
              >
                <div>
                  <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
                    {entry.title}
                  </h2>
                  <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                    {entry.subtitle}
                  </p>
                </div>
                <span
                  className="badge"
                  style={{
                    background: "#0b1b49",
                    color: "#fff",
                    borderColor: "#0b1b49",
                  }}
                >
                  Package
                </span>
              </div>

              <div className="panel" style={{ background: "#fafcff" }}>
                <div
                  className="metric-value"
                  style={{ fontSize: 38, marginTop: 0 }}
                >
                  {entry.priceLabel}
                </div>
                <div style={{ color: "#475569" }}>{entry.leadLine}</div>
              </div>

              {entry.features.length > 0 && (
                <ul style={{ margin: 0, paddingLeft: 18, color: "#334155" }}>
                  {entry.features.map((feature) => (
                    <li key={feature} style={{ marginBottom: 6 }}>
                      {feature}
                    </li>
                  ))}
                </ul>
              )}

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleCheckout(entry)}
                disabled={checkoutKey === entry.key || checkoutBlocked}
              >
                {checkoutKey === entry.key
                  ? "Opening Checkout..."
                  : checkoutBlocked
                    ? "License Verification Required"
                    : "Checkout"}
              </button>

              <button type="button" className="btn btn-secondary">
                View Details
              </button>
            </article>
          ))
        )}
      </section>
    </div>
  );
};

export default SubscriptionPage;
