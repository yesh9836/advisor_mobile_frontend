import { useEffect, useState } from "react";

import {
  getAdminPlans,
  getFirstPurchaseOfferConfig,
  updateFirstPurchaseOfferConfig,
} from "@/api/admin";
import type {
  FirstPurchaseAddonOfferConfig,
  FirstPurchaseAddonOfferUpdatePayload,
} from "@/types/purchase";
import type { AdminPlanItem } from "@/types/admin";
import { getApiErrorMessage, parseApiError } from "@/utils/api-error";

const toLocalDateTimeInputValue = (isoValue: string | null): string => {
  if (!isoValue) {
    return "";
  }
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const hour = String(parsed.getHours()).padStart(2, "0");
  const minute = String(parsed.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
};

const toIsoOrNull = (value: string): string | null => {
  const clean = value.trim();
  if (!clean) {
    return null;
  }

  const parsed = new Date(clean);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return parsed.toISOString();
};

const formatMoney = (value: number, currency: string): string => {
  return (value / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatDateTime = (isoValue: string): string => {
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) {
    return isoValue;
  }
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const centsToDollarInputValue = (value: number | null): string => {
  if (value === null || value === undefined) {
    return "";
  }
  return (value / 100).toFixed(2);
};

const dollarsInputToCents = (value: string): number | null => {
  const clean = value.trim();
  if (!clean) {
    return null;
  }

  if (!/^\d+(\.\d{1,2})?$/.test(clean)) {
    return null;
  }
  const parsed = Number.parseFloat(clean);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.round(parsed * 100);
};

interface OfferFormState {
  is_enabled: boolean;
  trigger_package_id: string;
  offer_credits_total: string;
  offer_price_dollars: string;
  headline: string;
  message: string;
  cta_label: string;
  starts_at: string;
  ends_at: string;
}

const defaultOfferFormState: OfferFormState = {
  is_enabled: false,
  trigger_package_id: "",
  offer_credits_total: "",
  offer_price_dollars: "",
  headline: "",
  message: "",
  cta_label: "",
  starts_at: "",
  ends_at: "",
};

const buildFormFromConfig = (config: FirstPurchaseAddonOfferConfig): OfferFormState => {
  return {
    is_enabled: config.is_enabled,
    trigger_package_id: config.trigger_package_id ? String(config.trigger_package_id) : "",
    offer_credits_total: config.offer_credits_total ? String(config.offer_credits_total) : "",
    offer_price_dollars: centsToDollarInputValue(config.offer_price_cents),
    headline: config.headline ?? "",
    message: config.message ?? "",
    cta_label: config.cta_label ?? "",
    starts_at: toLocalDateTimeInputValue(config.starts_at),
    ends_at: toLocalDateTimeInputValue(config.ends_at),
  };
};

const buildPayloadFromConfig = (
  config: FirstPurchaseAddonOfferConfig,
  options: { isEnabled: boolean },
): FirstPurchaseAddonOfferUpdatePayload => ({
  is_enabled: options.isEnabled,
  trigger_package_id: config.trigger_package_id,
  offer_credits_total: config.offer_credits_total,
  offer_price_cents: config.offer_price_cents,
  offer_currency: "USD",
  headline: config.headline,
  message: config.message,
  cta_label: config.cta_label,
  starts_at: config.starts_at,
  ends_at: config.ends_at,
});

const TRIGGER_PLAN_PAGE_SIZE = 100;

const getAllUnarchivedTriggerPlans = async (): Promise<AdminPlanItem[]> => {
  let page = 1;
  let total = 0;
  const rows: AdminPlanItem[] = [];

  do {
    const response = await getAdminPlans(page, TRIGGER_PLAN_PAGE_SIZE, {
      archived: "unarchived",
    });
    rows.push(...response.items);
    total = response.total;
    page += 1;
  } while ((page - 1) * TRIGGER_PLAN_PAGE_SIZE < total);

  return rows;
};

const FirstPurchaseOfferPage = () => {
  const [triggerPlans, setTriggerPlans] = useState<AdminPlanItem[]>([]);
  const [config, setConfig] = useState<FirstPurchaseAddonOfferConfig | null>(null);
  const [form, setForm] = useState<OfferFormState>(defaultOfferFormState);
  const [isEditingExistingOffer, setIsEditingExistingOffer] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [plans, currentConfig] = await Promise.all([
          getAllUnarchivedTriggerPlans(),
          getFirstPurchaseOfferConfig(),
        ]);
        if (!active) {
          return;
        }

        setTriggerPlans(plans);
        setConfig(currentConfig);
        setForm(defaultOfferFormState);
        setIsEditingExistingOffer(false);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(getApiErrorMessage(loadError, "Unable to load first-purchase offer settings."));
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void load();

    return () => {
      active = false;
    };
  }, []);

  const handleSave = async () => {
    setError(null);
    setSuccess(null);

    if (form.is_enabled) {
      if (!form.trigger_package_id || !form.offer_credits_total || !form.offer_price_dollars) {
        setError("Enabled offers require trigger package, add-on leads, and add-on price.");
        return;
      }
      const credits = Number(form.offer_credits_total);
      const priceCents = dollarsInputToCents(form.offer_price_dollars);
      if (!Number.isFinite(credits) || credits <= 0 || !Number.isInteger(credits)) {
        setError("Add-on leads must be a positive whole number.");
        return;
      }
      if (priceCents === null || priceCents <= 0) {
        setError("Add-on price must be a valid dollar amount (for example, 75.00).");
        return;
      }
    }

    if (form.starts_at && form.ends_at) {
      const startValue = new Date(form.starts_at).getTime();
      const endValue = new Date(form.ends_at).getTime();
      if (Number.isNaN(startValue) || Number.isNaN(endValue) || endValue < startValue) {
        setError("End time must be after start time.");
        return;
      }
    }

    const payload: FirstPurchaseAddonOfferUpdatePayload = {
      is_enabled: form.is_enabled,
      trigger_package_id: form.trigger_package_id ? Number(form.trigger_package_id) : null,
      offer_credits_total: form.offer_credits_total ? Number(form.offer_credits_total) : null,
      offer_price_cents: dollarsInputToCents(form.offer_price_dollars),
      offer_currency: "USD",
      headline: form.headline.trim() || null,
      message: form.message.trim() || null,
      cta_label: form.cta_label.trim() || null,
      starts_at: toIsoOrNull(form.starts_at),
      ends_at: toIsoOrNull(form.ends_at),
    };

    setSaving(true);
    try {
      const saved = await updateFirstPurchaseOfferConfig(payload);
      setConfig(saved);
      setForm(defaultOfferFormState);
      setIsEditingExistingOffer(false);
      setSuccess("First-purchase add-on offer saved.");
    } catch (saveError) {
      const parsedError = parseApiError(saveError, "Unable to save first-purchase offer settings.");
      setError(parsedError.code ? `${parsedError.code}: ${parsedError.message}` : parsedError.message);
    } finally {
      setSaving(false);
    }
  };

  const handleEditExistingOffer = () => {
    if (!config || config.id === null) return;
    setForm(buildFormFromConfig(config));
    setIsEditingExistingOffer(true);
    setError(null);
    setSuccess(null);
  };

  const handleArchiveToggle = async () => {
    if (!config || config.id === null) return;

    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const nextEnabled = !config.is_enabled;
      const saved = await updateFirstPurchaseOfferConfig(
        buildPayloadFromConfig(config, { isEnabled: nextEnabled }),
      );
      setConfig(saved);
      setForm(defaultOfferFormState);
      setIsEditingExistingOffer(false);
      setSuccess(nextEnabled ? "Offer unarchived." : "Offer archived.");
    } catch (saveError) {
      const parsedError = parseApiError(saveError, "Unable to update offer lifecycle.");
      setError(parsedError.code ? `${parsedError.code}: ${parsedError.message}` : parsedError.message);
    } finally {
      setSaving(false);
    }
  };

  const previewPriceCents = dollarsInputToCents(form.offer_price_dollars);

  return (
    <div className="page">
      <div>
        <h1>Admin • First Purchase Offer</h1>
        <p className="page-subtitle">
          Configure the one-time add-on checkout offer shown after an advisor completes their first purchase.
        </p>
      </div>

      {error && <div className="alert">{error}</div>}
      {success && <div className="success">{success}</div>}

      {loading ? (
        <section className="panel">
          <div className="metric-note">Loading offer configuration...</div>
        </section>
      ) : (
        <>
          <section className="panel stack">
          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#202860" }}>
                {isEditingExistingOffer ? "Edit Offer" : "Create Offer"}
              </h2>
              <p style={{ margin: "4px 0 0 0", color: "#58707d" }}>
                Advisors qualify only on the redirect from their first completed checkout.
              </p>
            </div>
            <label className="row" style={{ gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={form.is_enabled}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    is_enabled: event.target.checked,
                  }))
                }
              />
              <span style={{ color: "#0f172a", fontWeight: 600 }}>Enable Offer</span>
            </label>
          </div>

          {config?.inventory_ready !== null && config?.inventory_ready !== undefined && (
            <div
              className={config.inventory_ready ? "success" : "alert"}
              data-testid="offer-inventory-status"
            >
              {config.inventory_ready
                ? `Inventory ready for add-on checkout (${config.inventory_available_count ?? 0}/${config.inventory_required_count ?? 0} available).`
                : (config.inventory_gate_message ?? "Inventory is below the required threshold for add-on checkout.")}
              {!config.inventory_ready && config.inventory_gate_code && (
                <div style={{ marginTop: 6, fontWeight: 600 }}>
                  Code: {config.inventory_gate_code}
                </div>
              )}
            </div>
          )}

          <div className="grid-3">
            <div className="field">
              <label htmlFor="offer-trigger-package">Purchased Package (Trigger)</label>
              <select
                id="offer-trigger-package"
                value={form.trigger_package_id}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    trigger_package_id: event.target.value,
                  }))
                }
              >
                <option value="">Select package</option>
                {triggerPlans.map((plan) => (
                  <option key={plan.id} value={String(plan.id)}>
                    {plan.name} • {formatMoney(plan.price_cents, plan.currency)}
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <label htmlFor="offer-add-on-leads">Add-on Leads</label>
              <input
                id="offer-add-on-leads"
                type="number"
                min={1}
                step={1}
                value={form.offer_credits_total}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    offer_credits_total: event.target.value,
                  }))
                }
                placeholder="5"
              />
            </div>

            <div className="field">
              <label htmlFor="offer-add-on-price-dollars">Add-on Price (Dollars)</label>
              <input
                id="offer-add-on-price-dollars"
                type="number"
                min={0.01}
                step={0.01}
                value={form.offer_price_dollars}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    offer_price_dollars: event.target.value,
                  }))
                }
                placeholder="75.00"
              />
            </div>

            <div className="field">
              <label>Currency</label>
              <div style={{ color: "#0f172a", fontWeight: 600, paddingTop: 8 }}>USD</div>
            </div>

            <div className="field">
              <label htmlFor="offer-cta-label">CTA Label</label>
              <input
                id="offer-cta-label"
                value={form.cta_label}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    cta_label: event.target.value,
                  }))
                }
                placeholder="Upgrade package"
                maxLength={80}
              />
            </div>

            <div className="field">
              <label htmlFor="offer-headline">Headline</label>
              <input
                id="offer-headline"
                value={form.headline}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    headline: event.target.value,
                  }))
                }
                placeholder="First purchase bonus"
                maxLength={120}
              />
            </div>

            <div className="field" style={{ gridColumn: "span 2" }}>
              <label htmlFor="offer-message">Message</label>
              <textarea
                id="offer-message"
                value={form.message}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    message: event.target.value,
                  }))
                }
                placeholder="Upgrade this order to get extra lead credits right away."
                maxLength={400}
                rows={4}
              />
            </div>

            <div className="field">
              <label htmlFor="offer-start">Start (optional)</label>
              <input
                id="offer-start"
                type="datetime-local"
                value={form.starts_at}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    starts_at: event.target.value,
                  }))
                }
              />
            </div>

            <div className="field">
              <label htmlFor="offer-end">End (optional)</label>
              <input
                id="offer-end"
                type="datetime-local"
                value={form.ends_at}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    ends_at: event.target.value,
                  }))
                }
              />
            </div>
          </div>

          {form.offer_credits_total && form.offer_price_dollars && (
            <div className="panel" style={{ background: "#f4fbfc" }}>
              <div style={{ color: "#334a57" }}>
                Preview add-on: <strong>{form.offer_credits_total} leads</strong>
              </div>
              <div style={{ color: "#334a57" }}>
                {formatMoney(
                  previewPriceCents ?? 0,
                  "USD",
                )} • extra checkout after first completed purchase
              </div>
            </div>
          )}

          <div className="row" style={{ justifyContent: "flex-end", gap: 8 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => {
                setForm(defaultOfferFormState);
                setIsEditingExistingOffer(false);
                setError(null);
                setSuccess(null);
              }}
              disabled={saving}
            >
              Clear
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void handleSave()}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Offer"}
            </button>
          </div>

          </section>

          <section className="panel stack">
            <div className="page-header-row">
              <div>
                <h2 style={{ margin: 0, fontSize: 30, color: "#202860" }}>Existing Offers</h2>
                <p style={{ margin: "4px 0 0 0", color: "#58707d" }}>
                  Manage existing first-purchase offer configuration.
                </p>
              </div>
            </div>

            {config?.id ? (
              <article className="panel" style={{ background: "#f4fbfc" }}>
                <div className="page-header-row">
                  <div>
                    <div style={{ fontSize: 20, fontWeight: 800, color: "#202860" }}>
                      Offer #{config.id}
                    </div>
                    <div style={{ marginTop: 4, color: "#58707d" }}>
                      Status: {config.is_enabled ? "ACTIVE" : "ARCHIVED"} • Trigger:{" "}
                      {config.trigger_package_name ?? "Not set"}
                    </div>
                    <div style={{ marginTop: 4, color: "#58707d" }}>
                      Add-on:{" "}
                      {config.offer_price_cents !== null
                        ? formatMoney(config.offer_price_cents, config.offer_currency ?? "USD")
                        : "Not set"}{" "}
                      • {config.offer_credits_total ?? 0} leads
                    </div>
                    <div style={{ marginTop: 4, color: "#6d7f89", fontSize: 13 }}>
                      Window: {config.starts_at ? formatDateTime(config.starts_at) : "Not set"} →{" "}
                      {config.ends_at ? formatDateTime(config.ends_at) : "Not set"}
                    </div>
                    {config.updated_at && (
                      <div style={{ marginTop: 4, color: "#6d7f89", fontSize: 13 }}>
                        Last updated: {new Date(config.updated_at).toLocaleString("en-US")}
                      </div>
                    )}
                  </div>

                  <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={handleEditExistingOffer}
                      disabled={saving}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => void handleArchiveToggle()}
                      disabled={saving}
                    >
                      {saving
                        ? "Working..."
                        : (config.is_enabled ? "Archive" : "Unarchive")}
                    </button>
                  </div>
                </div>
              </article>
            ) : (
              <div style={{ color: "#58707d" }}>No offer config exists yet.</div>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default FirstPurchaseOfferPage;
