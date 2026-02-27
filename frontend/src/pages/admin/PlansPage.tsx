import { useCallback, useEffect, useMemo, useState } from "react";

import {
  archiveAdminPlan,
  createAdminPlan,
  getAdminPlans,
  unarchiveAdminPlan,
  updateAdminPlan,
} from "@/api/admin";
import type { AdminPlanItem } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

interface PlanFormState {
  name: string;
  priceDollars: string;
  creditsTotal: string;
  stateLimit: string;
  catalogVisible: boolean;
  effectiveFrom: string;
  effectiveTo: string;
}

const defaultPlanFormState: PlanFormState = {
  name: "",
  priceDollars: "",
  creditsTotal: "",
  stateLimit: "",
  catalogVisible: true,
  effectiveFrom: "",
  effectiveTo: "",
};
const PLAN_PAGE_SIZE = 20;

const centsToDollarInputValue = (value: number): string => (value / 100).toFixed(2);

const dollarsInputToCents = (value: string): number | null => {
  const clean = value.trim();
  if (!clean) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const parsed = Number.parseFloat(clean);
  if (!Number.isFinite(parsed)) return null;
  return Math.round(parsed * 100);
};

const toLocalDateTimeInputValue = (isoValue: string | null): string => {
  if (!isoValue) return "";
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) return "";
  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const hour = String(parsed.getHours()).padStart(2, "0");
  const minute = String(parsed.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hour}:${minute}`;
};

const toIsoOrNull = (value: string): string | null => {
  const clean = value.trim();
  if (!clean) return null;
  const parsed = new Date(clean);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toISOString();
};

const formatMoney = (amountCents: number, currency: string): string => {
  return (amountCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatDateTime = (isoValue: string | null): string => {
  if (!isoValue) return "Not set";
  const parsed = new Date(isoValue);
  if (Number.isNaN(parsed.getTime())) return isoValue;
  return parsed.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const lifecycleLabel = (plan: AdminPlanItem): string => {
  if (plan.is_archived) return "ARCHIVED";
  const now = Date.now();
  if (plan.effective_from && new Date(plan.effective_from).getTime() > now) return "SCHEDULED";
  if (plan.effective_to && new Date(plan.effective_to).getTime() < now) return "EXPIRED";
  return "ACTIVE";
};

const buildRequestId = (prefix: string): string => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`;
  }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
};

const PlansPage = () => {
  const [plans, setPlans] = useState<AdminPlanItem[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [archivedFilter, setArchivedFilter] = useState<"all" | "archived" | "unarchived">("all");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [actionInFlight, setActionInFlight] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [editingPlanId, setEditingPlanId] = useState<number | null>(null);
  const [form, setForm] = useState<PlanFormState>(defaultPlanFormState);

  const editingPlan = useMemo(
    () => plans.find((plan) => plan.id === editingPlanId) ?? null,
    [plans, editingPlanId],
  );
  const totalPages = Math.max(1, Math.ceil(total / PLAN_PAGE_SIZE));

  const loadPlans = useCallback(async (
    nextPage: number,
    nextSearch: string,
    nextArchivedFilter: "all" | "archived" | "unarchived",
  ) => {
    setLoading(true);
    setError(null);
    try {
      const response = await getAdminPlans(nextPage, PLAN_PAGE_SIZE, {
        search: nextSearch,
        archived: nextArchivedFilter,
      });
      setPlans(response.items);
      setTotal(response.total);
      setPage(response.page);
    } catch (loadError) {
      setPlans([]);
      setTotal(0);
      setError(getApiErrorMessage(loadError, "Unable to load admin plans."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPlans(1, "", "all");
  }, [loadPlans]);

  const resetForm = () => {
    setForm(defaultPlanFormState);
    setEditingPlanId(null);
  };

  const startEdit = (plan: AdminPlanItem) => {
    setEditingPlanId(plan.id);
    setForm({
      name: plan.name,
      priceDollars: centsToDollarInputValue(plan.price_cents),
      creditsTotal: String(plan.credits_total),
      stateLimit: plan.state_limit ? String(plan.state_limit) : "",
      catalogVisible: plan.catalog_visible,
      effectiveFrom: toLocalDateTimeInputValue(plan.effective_from),
      effectiveTo: toLocalDateTimeInputValue(plan.effective_to),
    });
    setError(null);
    setSuccess(null);
  };

  const validateForm = (): {
    name: string;
    priceCents: number;
    creditsTotal: number;
    stateLimit: number | null;
    effectiveFrom: string | null;
    effectiveTo: string | null;
  } | null => {
    const name = form.name.trim();
    if (!name) {
      setError("Plan name is required.");
      return null;
    }
    const priceCents = dollarsInputToCents(form.priceDollars);
    if (priceCents === null || priceCents <= 0) {
      setError("Price must be a valid positive dollar amount.");
      return null;
    }
    const creditsTotal = Number(form.creditsTotal);
    if (!Number.isFinite(creditsTotal) || creditsTotal <= 0 || !Number.isInteger(creditsTotal)) {
      setError("Credits must be a positive whole number.");
      return null;
    }
    let stateLimit: number | null = null;
    if (form.stateLimit.trim()) {
      const parsedStateLimit = Number(form.stateLimit);
      if (!Number.isFinite(parsedStateLimit) || parsedStateLimit <= 0 || !Number.isInteger(parsedStateLimit)) {
        setError("State limit must be a positive whole number when provided.");
        return null;
      }
      stateLimit = parsedStateLimit;
    }

    const effectiveFrom = toIsoOrNull(form.effectiveFrom);
    const effectiveTo = toIsoOrNull(form.effectiveTo);
    if (form.effectiveFrom.trim() && !effectiveFrom) {
      setError("Effective from date is invalid.");
      return null;
    }
    if (form.effectiveTo.trim() && !effectiveTo) {
      setError("Effective to date is invalid.");
      return null;
    }
    if (effectiveFrom && effectiveTo && new Date(effectiveTo).getTime() < new Date(effectiveFrom).getTime()) {
      setError("Effective to must be later than or equal to effective from.");
      return null;
    }

    return {
      name,
      priceCents,
      creditsTotal,
      stateLimit,
      effectiveFrom,
      effectiveTo,
    };
  };

  const handleCreate = async () => {
    setError(null);
    setSuccess(null);
    const parsed = validateForm();
    if (!parsed) return;

    setSubmitting(true);
    try {
      await createAdminPlan({
        name: parsed.name,
        price_cents: parsed.priceCents,
        credits_total: parsed.creditsTotal,
        state_limit: parsed.stateLimit,
        catalog_visible: form.catalogVisible,
        effective_from: parsed.effectiveFrom,
        effective_to: parsed.effectiveTo,
        request_id: buildRequestId("plan_create"),
      });
      setSuccess("Plan created.");
      resetForm();
      await loadPlans(1, search, archivedFilter);
    } catch (createError) {
      setError(getApiErrorMessage(createError, "Unable to create plan."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingPlan) return;
    setError(null);
    setSuccess(null);

    const parsed = validateForm();
    if (!parsed) return;

    const commercialChanged =
      parsed.priceCents !== editingPlan.price_cents || parsed.creditsTotal !== editingPlan.credits_total;
    if (commercialChanged && editingPlan.has_purchases) {
      setError("Commercial fields are immutable after purchases exist. Create a new plan instead.");
      return;
    }

    setSubmitting(true);
    try {
      await updateAdminPlan(editingPlan.id, {
        name: parsed.name,
        price_cents: parsed.priceCents,
        credits_total: parsed.creditsTotal,
        state_limit: parsed.stateLimit,
        catalog_visible: form.catalogVisible,
        effective_from: parsed.effectiveFrom,
        effective_to: parsed.effectiveTo,
        request_id: commercialChanged ? buildRequestId("plan_update") : undefined,
      });
      setSuccess("Plan updated.");
      resetForm();
      await loadPlans(1, search, archivedFilter);
    } catch (updateError) {
      setError(getApiErrorMessage(updateError, "Unable to update plan."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleArchiveToggle = async (plan: AdminPlanItem) => {
    const actionLabel = plan.is_archived ? "unarchive" : "archive";
    const confirmed = window.confirm(`Are you sure you want to ${actionLabel} "${plan.name}"?`);
    if (!confirmed) return;

    setActionInFlight(plan.id);
    setError(null);
    setSuccess(null);
    try {
      if (plan.is_archived) {
        await unarchiveAdminPlan(plan.id);
        setSuccess(`Plan "${plan.name}" unarchived.`);
      } else {
        await archiveAdminPlan(plan.id);
        setSuccess(`Plan "${plan.name}" archived.`);
      }
      await loadPlans(1, search, archivedFilter);
    } catch (actionError) {
      setError(getApiErrorMessage(actionError, `Unable to ${actionLabel} plan.`));
    } finally {
      setActionInFlight(null);
    }
  };

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • Plans</h1>
          <p className="page-subtitle">
            Create, edit, archive, and schedule plan availability windows for one-time purchases.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void loadPlans(page, search, archivedFilter)}
          disabled={loading}
        >
          Refresh
        </button>
      </div>

      {error && <div className="alert">{error}</div>}
      {success && <div className="success">{success}</div>}

      <section className="panel stack">
        <div className="page-header-row">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>
              {editingPlan ? `Edit Plan #${editingPlan.id}` : "Create Plan"}
            </h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Commercial fields (price + credits) lock after purchases exist.
            </p>
          </div>
          {editingPlan && (
            <button type="button" className="btn btn-secondary" onClick={resetForm} disabled={submitting}>
              Cancel Edit
            </button>
          )}
        </div>

        <div className="grid-3">
          <div className="field">
            <label htmlFor="plan-name">Plan Name</label>
            <input
              id="plan-name"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Growth 25"
            />
          </div>
          <div className="field">
            <label htmlFor="plan-price">Price (USD)</label>
            <input
              id="plan-price"
              value={form.priceDollars}
              onChange={(event) => setForm((prev) => ({ ...prev, priceDollars: event.target.value }))}
              placeholder="199.00"
            />
          </div>
          <div className="field">
            <label htmlFor="plan-credits">Credits</label>
            <input
              id="plan-credits"
              value={form.creditsTotal}
              onChange={(event) => setForm((prev) => ({ ...prev, creditsTotal: event.target.value }))}
              placeholder="25"
            />
          </div>
          <div className="field">
            <label htmlFor="plan-state-limit">State Limit (optional)</label>
            <input
              id="plan-state-limit"
              value={form.stateLimit}
              onChange={(event) => setForm((prev) => ({ ...prev, stateLimit: event.target.value }))}
              placeholder="3"
            />
          </div>
          <div className="field">
            <label htmlFor="plan-effective-from">Effective From (optional)</label>
            <input
              id="plan-effective-from"
              type="datetime-local"
              value={form.effectiveFrom}
              onChange={(event) => setForm((prev) => ({ ...prev, effectiveFrom: event.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="plan-effective-to">Effective To (optional)</label>
            <input
              id="plan-effective-to"
              type="datetime-local"
              value={form.effectiveTo}
              onChange={(event) => setForm((prev) => ({ ...prev, effectiveTo: event.target.value }))}
            />
          </div>
        </div>

        <label className="row" style={{ alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={form.catalogVisible}
            onChange={(event) => setForm((prev) => ({ ...prev, catalogVisible: event.target.checked }))}
          />
          <span style={{ color: "#0f172a", fontWeight: 600 }}>Show in advisor catalog</span>
        </label>

        <div className="row">
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void (editingPlan ? handleUpdate() : handleCreate())}
            disabled={submitting}
          >
            {submitting
              ? (editingPlan ? "Saving..." : "Creating...")
              : (editingPlan ? "Save Plan" : "Create Plan")}
          </button>
        </div>
      </section>

      <section className="panel stack">
        <div className="page-header-row">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Existing Plans</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Filter and manage lifecycle state.
            </p>
          </div>
        </div>

        <div className="row" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="field" style={{ minWidth: 220 }}>
            <label htmlFor="plan-search">Search</label>
            <input
              id="plan-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search plan name"
            />
          </div>
          <div className="field" style={{ minWidth: 200 }}>
            <label htmlFor="plan-archived-filter">Archived Filter</label>
            <select
              id="plan-archived-filter"
              value={archivedFilter}
              onChange={(event) =>
                setArchivedFilter(event.target.value as "all" | "archived" | "unarchived")
              }
            >
              <option value="all">All</option>
              <option value="unarchived">Unarchived</option>
              <option value="archived">Archived</option>
            </select>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void loadPlans(1, search, archivedFilter)}
          >
            Apply Filters
          </button>
        </div>

        {loading && <div style={{ color: "#475569" }}>Loading plans...</div>}

        {!loading && plans.length === 0 && (
          <div style={{ color: "#475569" }}>No plans found for the selected filter.</div>
        )}

        {!loading && plans.map((plan) => (
          <article key={plan.id} className="panel" style={{ background: "#f8fafc" }}>
            <div className="page-header-row">
              <div>
                <div style={{ fontSize: 20, fontWeight: 800, color: "#0b1b49" }}>
                  {plan.name}
                </div>
                <div style={{ marginTop: 4, color: "#475569" }}>
                  {formatMoney(plan.price_cents, plan.currency)} • {plan.credits_total} credits
                  {plan.state_limit ? ` • ${plan.state_limit} state limit` : " • no state limit"}
                </div>
                <div style={{ marginTop: 4, color: "#64748b", fontSize: 13 }}>
                  Lifecycle: {lifecycleLabel(plan)} • Catalog: {plan.catalog_visible ? "VISIBLE" : "HIDDEN"} •
                  Purchases: {plan.has_purchases ? "YES" : "NO"}
                </div>
                <div style={{ marginTop: 4, color: "#64748b", fontSize: 13 }}>
                  Effective: {formatDateTime(plan.effective_from)} → {formatDateTime(plan.effective_to)}
                </div>
              </div>
              <div className="row" style={{ flexWrap: "wrap" }}>
                <button type="button" className="btn btn-secondary" onClick={() => startEdit(plan)}>
                  Edit
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => void handleArchiveToggle(plan)}
                  disabled={actionInFlight === plan.id}
                >
                  {actionInFlight === plan.id
                    ? "Working..."
                    : (plan.is_archived ? "Unarchive" : "Archive")}
                </button>
              </div>
            </div>
          </article>
        ))}

        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: "#475569", fontSize: 14 }}>
            Page {page} of {totalPages} • {total} total plans
          </span>

          <div className="row">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || page <= 1}
              onClick={() => void loadPlans(Math.max(1, page - 1), search, archivedFilter)}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || page >= totalPages}
              onClick={() => void loadPlans(page + 1, search, archivedFilter)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default PlansPage;
