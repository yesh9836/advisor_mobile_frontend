import { useCallback, useEffect, useMemo, useState } from "react";

import { getMyGoal, saveMyGoal } from "@/api/goals";
import { createCheckout } from "@/api/purchases";
import {
  basisPointsToPercentInput,
  calculateGoalPreview,
  centsToDollarsInput,
  formatCompactMoney,
  formatNumber,
  formatWholeMoney,
  parseMoneyToCents,
  parsePercentToBasisPoints,
  recalculatePackageRecommendation,
} from "@/pages/advisor/goalCalculations";
import type {
  AdvisorGoalResponse,
  AdvisorGoalUpdatePayload,
  GoalDerived,
  GoalPackageRecommendation,
} from "@/types/goal";
import { getApiErrorMessage } from "@/utils/api-error";
import { isRequestCanceled, useLatestRequest } from "@/utils/request-control";

interface GoalFormState {
  targetYear: string;
  annualIncomeGoal: string;
  averageCommission: string;
  earnedYtd: string;
  appointmentToDealRate: string;
  leadToAppointmentRate: string;
}

const toFormState = (response: AdvisorGoalResponse): GoalFormState => ({
  targetYear: String(response.goal.target_year),
  annualIncomeGoal: centsToDollarsInput(response.goal.annual_income_goal_cents),
  averageCommission: centsToDollarsInput(response.goal.average_commission_cents),
  earnedYtd: centsToDollarsInput(response.goal.earned_ytd_cents),
  appointmentToDealRate: basisPointsToPercentInput(
    response.goal.appointment_to_deal_rate_bps,
  ),
  leadToAppointmentRate: basisPointsToPercentInput(
    response.goal.lead_to_appointment_rate_bps,
  ),
});

const buildPayload = (form: GoalFormState): AdvisorGoalUpdatePayload | null => {
  const targetYear = Number(form.targetYear);
  const annualIncomeGoal = parseMoneyToCents(form.annualIncomeGoal);
  const averageCommission = parseMoneyToCents(form.averageCommission);
  const earnedYtd = parseMoneyToCents(form.earnedYtd);
  const appointmentToDealRate = parsePercentToBasisPoints(
    form.appointmentToDealRate,
  );
  const leadToAppointmentRate = parsePercentToBasisPoints(
    form.leadToAppointmentRate,
  );

  if (
    !Number.isInteger(targetYear) ||
    annualIncomeGoal === null ||
    averageCommission === null ||
    earnedYtd === null ||
    appointmentToDealRate === null ||
    leadToAppointmentRate === null
  ) {
    return null;
  }

  return {
    target_year: targetYear,
    annual_income_goal_cents: annualIncomeGoal,
    average_commission_cents: averageCommission,
    earned_ytd_cents: earnedYtd,
    appointment_to_deal_rate_bps: appointmentToDealRate,
    lead_to_appointment_rate_bps: leadToAppointmentRate,
  };
};

const validatePayload = (payload: AdvisorGoalUpdatePayload | null): string | null => {
  if (!payload) {
    return "Enter valid numeric values for every goal field.";
  }
  if (payload.target_year < 2000 || payload.target_year > 2100) {
    return "Target year must be between 2000 and 2100.";
  }
  if (payload.annual_income_goal_cents <= 0) {
    return "Annual income goal must be greater than zero.";
  }
  if (payload.average_commission_cents <= 0) {
    return "Average commission must be greater than zero.";
  }
  if (payload.earned_ytd_cents < 0) {
    return "Earned year-to-date cannot be negative.";
  }
  if (
    payload.appointment_to_deal_rate_bps < 1 ||
    payload.appointment_to_deal_rate_bps > 10000 ||
    payload.lead_to_appointment_rate_bps < 1 ||
    payload.lead_to_appointment_rate_bps > 10000
  ) {
    return "Rates must be between 0.01% and 100%.";
  }
  return null;
};

const rankRecommendations = (
  packages: GoalPackageRecommendation[],
  leadsRemaining: number,
): GoalPackageRecommendation[] => {
  const recalculated = packages.map((item) =>
    recalculatePackageRecommendation(item, leadsRemaining),
  );
  const best = recalculated.reduce<GoalPackageRecommendation | null>(
    (currentBest, item) => {
      if (!currentBest) {
        return item;
      }
      if (item.total_cost_cents < currentBest.total_cost_cents) {
        return item;
      }
      if (
        item.total_cost_cents === currentBest.total_cost_cents &&
        item.packages_needed < currentBest.packages_needed
      ) {
        return item;
      }
      return currentBest;
    },
    null,
  );
  return recalculated.map((item) => ({
    ...item,
    recommended: best?.package_id === item.package_id,
  }));
};

const GoalsPage = () => {
  const [goalResponse, setGoalResponse] = useState<AdvisorGoalResponse | null>(
    null,
  );
  const [form, setForm] = useState<GoalFormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [checkoutPackageId, setCheckoutPackageId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const { beginRequest, isLatestRequest } = useLatestRequest();

  const loadGoal = useCallback(async () => {
    const { requestId, signal } = beginRequest();
    setLoading(true);
    setError(null);
    try {
      const response = await getMyGoal(undefined, { signal });
      if (!isLatestRequest(requestId)) {
        return;
      }
      setGoalResponse(response);
      setForm(toFormState(response));
    } catch (loadError) {
      if (!isLatestRequest(requestId) || isRequestCanceled(loadError)) {
        return;
      }
      setError(getApiErrorMessage(loadError, "Unable to load goals."));
      setGoalResponse(null);
      setForm(null);
    } finally {
      if (isLatestRequest(requestId)) {
        setLoading(false);
      }
    }
  }, [beginRequest, isLatestRequest]);

  useEffect(() => {
    void loadGoal();
  }, [loadGoal]);

  const payload = useMemo(() => (form ? buildPayload(form) : null), [form]);
  const validationMessage = validatePayload(payload);

  const derived: GoalDerived | null = useMemo(() => {
    if (!payload || !goalResponse) {
      return goalResponse?.derived ?? null;
    }
    return calculateGoalPreview(
      payload,
      goalResponse.derived.closed_deals_ytd,
    );
  }, [goalResponse, payload]);

  const packageRecommendations = useMemo(() => {
    if (!goalResponse || !derived) {
      return [];
    }
    return rankRecommendations(goalResponse.packages, derived.leads_remaining);
  }, [derived, goalResponse]);

  const updateField = (field: keyof GoalFormState, value: string) => {
    setForm((previous) => (previous ? { ...previous, [field]: value } : previous));
    setSaveMessage(null);
  };

  const handleSave = async () => {
    if (validationMessage || !payload) {
      setError(validationMessage ?? "Unable to save invalid goal values.");
      return;
    }

    setSaving(true);
    setError(null);
    setSaveMessage(null);
    try {
      const response = await saveMyGoal(payload);
      setGoalResponse(response);
      setForm(toFormState(response));
      setSaveMessage("Goal saved.");
      window.setTimeout(() => setSaveMessage(null), 2400);
    } catch (saveError) {
      setError(getApiErrorMessage(saveError, "Unable to save goal."));
    } finally {
      setSaving(false);
    }
  };

  const handleCheckout = async (packageId: number) => {
    setCheckoutPackageId(packageId);
    setError(null);
    try {
      const checkout = await createCheckout(packageId);
      window.location.assign(checkout.url);
    } catch (checkoutError) {
      setError(getApiErrorMessage(checkoutError, "Unable to start checkout."));
      setCheckoutPackageId(null);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <div className="page-header-row">
          <div>
            <h1>Goals</h1>
            <p className="page-subtitle">Loading your saved income plan...</p>
          </div>
        </div>
        <section className="panel">Loading goals...</section>
      </div>
    );
  }

  if (!form || !derived || !goalResponse) {
    return (
      <div className="page">
        <div className="page-header-row">
          <div>
            <h1>Goals</h1>
            <p className="page-subtitle">
              Set an annual income target and the lead volume needed to hit it.
            </p>
          </div>
          <button type="button" className="btn btn-secondary" onClick={() => void loadGoal()}>
            Retry
          </button>
        </div>
        {error && <div className="alert">{error}</div>}
      </div>
    );
  }

  const progress = Math.min(Math.max(derived.income_progress_percent, 0), 100);

  return (
    <div className="page goals-page">
      <div className="page-header-row">
        <div>
          <h1>Goals</h1>
          <p className="page-subtitle">
            Set your annual income target and track how many leads you need to
            hit it.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void handleSave()}
          disabled={saving || Boolean(validationMessage)}
        >
          {saving ? "Saving..." : "Save Goal"}
        </button>
      </div>

      {error && <div className="alert">{error}</div>}
      {validationMessage && <div className="alert">{validationMessage}</div>}
      {saveMessage && <div className="success">{saveMessage}</div>}

      <section className="goals-hero" aria-label="Income goal progress">
        <div className="goals-hero-main">
          <p className="goals-kicker">{form.targetYear} Income Goal</p>
          <strong>{formatWholeMoney(payload?.annual_income_goal_cents ?? 0)}</strong>
        </div>
        <div className="goals-hero-earned">
          <p className="goals-kicker">Earned YTD</p>
          <strong>{formatWholeMoney(payload?.earned_ytd_cents ?? 0)}</strong>
          <span>{progress}% there</span>
        </div>
        <div className="goals-progress-track">
          <div className="goals-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="goals-hero-stats">
          <div>
            <span>Deals to close</span>
            <strong>{formatNumber(derived.deals_remaining)}</strong>
          </div>
          <div>
            <span>Appts needed</span>
            <strong>{formatNumber(derived.appointments_remaining)}</strong>
          </div>
          <div>
            <span>Leads needed</span>
            <strong>{formatNumber(derived.leads_remaining)}</strong>
          </div>
          <div>
            <span>Est. lead cost</span>
            <strong>
              {packageRecommendations.length > 0
                ? formatWholeMoney(
                    Math.min(
                      ...packageRecommendations.map((item) => item.total_cost_cents),
                    ),
                  )
                : "N/A"}
            </strong>
          </div>
        </div>
      </section>

      <div className="goals-main-grid">
        <section className="panel goals-form-panel">
          <div>
            <h2>Your Funnel</h2>
            <p className="metric-note">
              Adjust your inputs and save when the annual plan looks right.
            </p>
          </div>
          <div className="goals-form-grid">
            <div className="field">
              <label htmlFor="target-year">Target year</label>
              <input
                id="target-year"
                inputMode="numeric"
                value={form.targetYear}
                onChange={(event) => updateField("targetYear", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="annual-income-goal">Annual income goal</label>
              <input
                id="annual-income-goal"
                inputMode="decimal"
                value={form.annualIncomeGoal}
                onChange={(event) =>
                  updateField("annualIncomeGoal", event.target.value)
                }
              />
            </div>
            <div className="field">
              <label htmlFor="average-commission">Avg commission per deal</label>
              <input
                id="average-commission"
                inputMode="decimal"
                value={form.averageCommission}
                onChange={(event) =>
                  updateField("averageCommission", event.target.value)
                }
              />
            </div>
            <div className="field">
              <label htmlFor="earned-ytd">Earned year-to-date</label>
              <input
                id="earned-ytd"
                inputMode="decimal"
                value={form.earnedYtd}
                onChange={(event) => updateField("earnedYtd", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="appointment-to-deal-rate">
                Closing rate (appt to deal)
              </label>
              <div className="goals-input-suffix">
                <input
                  id="appointment-to-deal-rate"
                  inputMode="decimal"
                  value={form.appointmentToDealRate}
                  onChange={(event) =>
                    updateField("appointmentToDealRate", event.target.value)
                  }
                />
                <span>%</span>
              </div>
            </div>
            <div className="field">
              <label htmlFor="lead-to-appointment-rate">
                Lead to appointment rate
              </label>
              <div className="goals-input-suffix">
                <input
                  id="lead-to-appointment-rate"
                  inputMode="decimal"
                  value={form.leadToAppointmentRate}
                  onChange={(event) =>
                    updateField("leadToAppointmentRate", event.target.value)
                  }
                />
                <span>%</span>
              </div>
            </div>
          </div>
        </section>

        <aside className="panel goals-breakdown">
          <h2>Funnel Breakdown</h2>
          <p className="metric-note">From lead to closed deal.</p>
          {[
            {
              label: "Leads",
              value: derived.leads_needed,
              note: `${form.leadToAppointmentRate}% appt rate`,
              percent: 100,
            },
            {
              label: "Appointments",
              value: derived.appointments_needed,
              note: `${form.appointmentToDealRate}% closing rate`,
              percent: (derived.appointments_needed / derived.leads_needed) * 100,
            },
            {
              label: "Closed Deals",
              value: derived.deals_needed,
              note: `${formatCompactMoney(payload?.average_commission_cents ?? 0)} avg`,
              percent: (derived.deals_needed / derived.leads_needed) * 100,
            },
            {
              label: "Income Target",
              value: formatWholeMoney(payload?.annual_income_goal_cents ?? 0),
              note: "annual goal",
              percent: (derived.deals_needed / derived.leads_needed) * 100,
            },
          ].map((row) => (
            <div key={row.label} className="goals-breakdown-row">
              <div>
                <strong>{row.label}</strong>
                <span>{row.note}</span>
              </div>
              <b>{typeof row.value === "number" ? formatNumber(row.value) : row.value}</b>
              <div className="goals-mini-track">
                <div
                  style={{ width: `${Math.max(Math.min(row.percent, 100), 8)}%` }}
                />
              </div>
            </div>
          ))}
          <div className="goals-actuals">
            <span>Actual closed deals YTD</span>
            <strong>{formatNumber(derived.closed_deals_ytd)}</strong>
          </div>
          <div className="goals-actuals">
            <span>Estimated from manual earned YTD</span>
            <strong>{formatNumber(derived.estimated_deals_from_earned_ytd)}</strong>
          </div>
        </aside>
      </div>

      <section className="panel goals-recommendations">
        <div className="goals-recommendation-header">
          <div>
            <h2>Recommended Lead Volume</h2>
            <p className="metric-note">
              You need <strong>{formatNumber(derived.leads_remaining)} more leads</strong>{" "}
              to close <strong>{formatNumber(derived.deals_remaining)} deals</strong>{" "}
              and hit your goal.
            </p>
          </div>
          <span>Based on your funnel</span>
        </div>

        {packageRecommendations.length === 0 ? (
          <p className="metric-note">No current lead packages are available.</p>
        ) : (
          <div className="goals-package-grid">
            {packageRecommendations.map((item) => (
              <article
                key={item.package_id}
                className={`goals-package-card ${item.recommended ? "recommended" : ""}`}
              >
                {item.recommended && <span className="goals-package-pill">Recommended</span>}
                <p>{item.name}</p>
                <strong>
                  {formatCompactMoney(item.estimated_cost_per_lead_cents, item.currency)}
                  <small>/lead</small>
                </strong>
                <span>
                  {formatNumber(item.packages_needed)} package
                  {item.packages_needed === 1 ? "" : "s"} x{" "}
                  {formatNumber(item.credits_per_package)} leads
                </span>
                <b>{formatWholeMoney(item.total_cost_cents, item.currency)}</b>
                <button
                  type="button"
                  className={item.recommended ? "btn btn-secondary" : "btn btn-primary"}
                  onClick={() => void handleCheckout(item.package_id)}
                  disabled={checkoutPackageId !== null || saving}
                >
                  {checkoutPackageId === item.package_id
                    ? "Opening..."
                    : "Buy Package"}
                </button>
              </article>
            ))}
          </div>
        )}

        <div className="goals-pacing-tip">
          <strong>Pacing tip:</strong> {derived.pacing.message}
        </div>
      </section>
    </div>
  );
};

export default GoalsPage;
