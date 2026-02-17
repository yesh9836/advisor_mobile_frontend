import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  getMyDeliverySettings,
  updateMyDeliverySettings,
  type DeliverySettingsResponse,
  type DeliverySettingsUpdatePayload,
} from "@/api/delivery-settings";
import { getLeadDashboardSummary, getLeads } from "@/api/leads";
import type {
  Lead,
  LeadDashboardSummary,
  LeadOutcomeStatus,
} from "@/types/lead";
import { getApiErrorMessage } from "@/utils/api-error";

type LeadStage = "New" | "Contacted" | "Appointment Set";

interface RecentLeadItem {
  id: number;
  initials: string;
  name: string;
  state: string;
  stage: LeadStage;
  headline: string;
  assets: string;
  dateTime: string;
}

interface DeliverySettingsEditorState {
  email_alerts_enabled: boolean;
  sms_alerts_enabled: boolean;
  version: number | null;
  warnings: string[];
}

interface SettingsFeedback {
  kind: "success" | "error";
  message: string;
}

const toDisplayStage = (
  status: LeadOutcomeStatus | null | undefined,
): LeadStage => {
  if (status === "contacted") return "Contacted";
  if (status === "appointment_set") return "Appointment Set";
  return "New";
};

const toInitials = (
  firstName: string | null,
  lastName: string | null,
): string => {
  const first = firstName?.trim()?.[0] ?? "";
  const last = lastName?.trim()?.[0] ?? "";
  const initials = `${first}${last}`.toUpperCase();
  return initials || "NA";
};

const toDisplayName = (lead: Lead): string => {
  const first = lead.first_name?.trim() ?? "";
  const last = lead.last_name?.trim() ?? "";
  const full = `${first} ${last}`.trim();
  return full || "Unknown Lead";
};

const formatDateTime = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "Recently";
  }

  const datePart = parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const timePart = parsed.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });

  return `${datePart} • ${timePart}`;
};

const formatCurrency = (amount: number, currency: string): string => {
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const toRecentLead = (lead: Lead): RecentLeadItem => {
  return {
    id: lead.id,
    initials: toInitials(lead.first_name, lead.last_name),
    name: toDisplayName(lead),
    state: (lead.state_code || "NA").toUpperCase(),
    stage: toDisplayStage(lead.outcome_status),
    headline: lead.most_important_retirement_activity || "No details available",
    assets: lead.total_investable_assets_range || "0",
    dateTime: formatDateTime(lead.created_at),
  };
};

const stageClassName = (stage: LeadStage): string => {
  if (stage === "New") return "badge badge-new";
  if (stage === "Contacted") return "badge badge-contacted";
  return "badge badge-set";
};

const toEditorState = (
  settings: DeliverySettingsResponse,
): DeliverySettingsEditorState => ({
  email_alerts_enabled: settings.email_alerts_enabled,
  sms_alerts_enabled: settings.sms_alerts_enabled,
  version: settings.version,
  warnings: settings.warnings ?? [],
});

const toFallbackEditorState = (
  summary: LeadDashboardSummary | null,
): DeliverySettingsEditorState | null => {
  if (!summary?.settings) {
    return null;
  }
  return {
    email_alerts_enabled: summary.settings.email_alerts_enabled,
    sms_alerts_enabled: summary.settings.sms_alerts_enabled,
    version: null,
    warnings: [],
  };
};

const DashboardPage = () => {
  const navigate = useNavigate();

  const [recentLeads, setRecentLeads] = useState<RecentLeadItem[]>([]);
  const [summary, setSummary] = useState<LeadDashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSettingsEditorOpen, setIsSettingsEditorOpen] = useState(false);
  const [settingsEditorLoading, setSettingsEditorLoading] = useState(false);
  const [settingsPendingField, setSettingsPendingField] = useState<
    "email" | "sms" | null
  >(null);
  const [settingsFeedback, setSettingsFeedback] =
    useState<SettingsFeedback | null>(null);
  const [editorSettings, setEditorSettings] =
    useState<DeliverySettingsEditorState | null>(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);

      try {
        const [summaryResponse, leadsResponse] = await Promise.all([
          getLeadDashboardSummary(),
          getLeads(1, 3, { delivery_status: "delivered" }),
        ]);

        setSummary(summaryResponse);
        setRecentLeads(
          leadsResponse.items.slice(0, 3).map((lead) => toRecentLead(lead)),
        );
      } catch (loadError) {
        setSummary(null);
        setRecentLeads([]);
        setError(getApiErrorMessage(loadError, "Unable to load dashboard data."));
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

  const handleOpenSettingsEditor = async () => {
    setIsSettingsEditorOpen(true);
    setSettingsFeedback(null);
    setSettingsEditorLoading(true);

    try {
      const response = await getMyDeliverySettings();
      setEditorSettings(toEditorState(response));
    } catch (loadError) {
      setSettingsFeedback({
        kind: "error",
        message: getApiErrorMessage(
          loadError,
          "Unable to load delivery settings.",
        ),
      });
      setEditorSettings((current) => current ?? toFallbackEditorState(summary));
    } finally {
      setSettingsEditorLoading(false);
    }
  };

  const handleCloseSettingsEditor = () => {
    if (settingsPendingField !== null) {
      return;
    }
    setIsSettingsEditorOpen(false);
    setSettingsFeedback(null);
  };

  const handleInstantToggleUpdate = async (
    field: "email_alerts_enabled" | "sms_alerts_enabled",
  ) => {
    if (!editorSettings || settingsPendingField !== null) {
      return;
    }

    const previous = editorSettings;
    const nextValue = !previous[field];
    const pendingField = field === "email_alerts_enabled" ? "email" : "sms";
    const label = field === "email_alerts_enabled" ? "Email alerts" : "SMS alerts";

    setEditorSettings({
      ...previous,
      [field]: nextValue,
    });
    setSettingsFeedback(null);
    setSettingsPendingField(pendingField);

    try {
      const payload: DeliverySettingsUpdatePayload =
        field === "email_alerts_enabled"
          ? { email_alerts_enabled: nextValue }
          : { sms_alerts_enabled: nextValue };
      if (previous.version !== null) {
        payload.expected_version = previous.version;
      }
      const response = await updateMyDeliverySettings(payload);
      const updatedState = toEditorState(response);
      const updatedValue = field === "email_alerts_enabled"
        ? updatedState.email_alerts_enabled
        : updatedState.sms_alerts_enabled;
      setEditorSettings(updatedState);
      setSettingsFeedback({
        kind: "success",
        message: `${label} ${updatedValue ? "enabled" : "disabled"}.`,
      });
      try {
        const refreshedSummary = await getLeadDashboardSummary();
        setSummary(refreshedSummary);
      } catch {
        setSummary((current) => {
          if (!current) {
            return current;
          }
          return {
            ...current,
            settings: {
              ...current.settings,
              email_alerts_enabled: updatedState.email_alerts_enabled,
              sms_alerts_enabled: updatedState.sms_alerts_enabled,
            },
          };
        });
      }
    } catch (updateError) {
      setEditorSettings(previous);
      setSettingsFeedback({
        kind: "error",
        message: getApiErrorMessage(
          updateError,
          "Unable to update delivery settings.",
        ),
      });
    } finally {
      setSettingsPendingField(null);
    }
  };

  const settings = summary?.settings;

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Advisor Dashboard</h1>
          <p className="page-subtitle">
            Track your lead flow, performance, and delivery settings.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => navigate("/subscription")}
        >
          Buy More Leads
        </button>
      </div>

      {error && <div className="alert">{error}</div>}

      <section className="grid-3">
        <article className="panel">
          <div className="metric-title">Leads Delivered (7 days)</div>
          <div className="metric-value">
            {loading ? "..." : (summary?.leads_delivered_7_days ?? 0)}
          </div>
          <div className="metric-note">Pulled from current lead records</div>
        </article>
        <article className="panel">
          <div className="metric-title">Appointments Set (7 days)</div>
          <div className="metric-value">
            {loading ? "..." : (summary?.appointments_set_7_days ?? 0)}
          </div>
          <div className="metric-note">From saved lead outcomes</div>
        </article>
        <article className="panel">
          <div className="metric-title">Cost per Appointment</div>
          <div className="metric-value">
            {loading
              ? "..."
              : formatCurrency(
                  summary?.cost_per_appointment ?? 0,
                  summary?.currency ?? "USD",
                )}
          </div>
          <div className="metric-note">
            Current formula: plan price / appointments set (7 days)
          </div>
        </article>
      </section>

      <section className="grid-main">
        <article className="panel">
          <div className="page-header-row">
            <div>
              <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
                Recent Leads
              </h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Most recent deliveries across your states.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/leads")}
            >
              View Inbox
            </button>
          </div>

          {loading ? (
            <div className="metric-note">Loading recent leads...</div>
          ) : recentLeads.length === 0 ? (
            <div className="metric-note">No leads available</div>
          ) : (
            recentLeads.map((lead) => (
              <div key={lead.id} className="lead-row">
                <div className="lead-main">
                  <div className="avatar">{lead.initials}</div>
                  <div className="lead-text">
                    <div className="lead-name">
                      {lead.name}
                      <span style={{ color: "#64748b", fontSize: 13 }}>
                        • {lead.state}
                      </span>
                      <span className={stageClassName(lead.stage)}>
                        {lead.stage}
                      </span>
                    </div>
                    <div className="lead-sub">
                      {lead.headline} • <strong>{lead.assets}</strong>
                    </div>
                  </div>
                </div>
                <div className="lead-time">{lead.dateTime}</div>
              </div>
            ))
          )}
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
              Delivery Settings
            </h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Manage your notification preferences for lead delivery.
            </p>
          </div>

          <section className="panel" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16, color: "#0b1b49" }}>
              Notifications
            </h3>
            <div style={{ marginTop: 8, color: "#334155" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Email alerts</span>
                <strong data-testid="delivery-email-status">
                  {settings?.email_alerts_enabled ? "On" : "Off"}
                </strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>SMS alerts</span>
                <strong data-testid="delivery-sms-status">
                  {settings?.sms_alerts_enabled ? "On" : "Off"}
                </strong>
              </div>
            </div>
          </section>

          <section className="panel" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16, color: "#0b1b49" }}>
              Targeting
            </h3>
            <div style={{ marginTop: 8, color: "#334155" }}>
              <div>
                States:{" "}
                <strong>
                  {settings?.target_states?.length
                    ? settings.target_states.join(", ")
                    : "-"}
                </strong>
              </div>
              <div>
                Min assets: <strong>{settings?.min_assets ?? "Not set"}</strong>
              </div>
              <div>
                Daily lead cap:{" "}
                <strong>{settings?.daily_download_limit ?? "-"}</strong>
              </div>
            </div>
          </section>

          {settingsFeedback && (
            <div className={settingsFeedback.kind === "error" ? "alert" : "success"}>
              {settingsFeedback.message}
            </div>
          )}

          <button
            type="button"
            className="btn btn-primary"
            onClick={() =>
              isSettingsEditorOpen
                ? handleCloseSettingsEditor()
                : void handleOpenSettingsEditor()
            }
            disabled={settingsPendingField !== null}
          >
            {isSettingsEditorOpen ? "Close Settings" : "Edit Settings"}
          </button>

          {isSettingsEditorOpen && (
            <section className="panel stack" style={{ padding: 12, background: "#f8fafc" }}>
              <h3 style={{ margin: 0, fontSize: 16, color: "#0b1b49" }}>
                Notification Preferences
              </h3>
              {settingsEditorLoading ? (
                <div className="metric-note">Loading settings...</div>
              ) : (
                <>
                  <div className="settings-toggle-row">
                    <label htmlFor="email-alerts-toggle">Email alerts</label>
                    <input
                      id="email-alerts-toggle"
                      type="checkbox"
                      checked={editorSettings?.email_alerts_enabled ?? false}
                      onChange={() =>
                        void handleInstantToggleUpdate("email_alerts_enabled")
                      }
                      disabled={
                        !editorSettings || settingsPendingField !== null
                      }
                    />
                  </div>
                  <div className="settings-toggle-row">
                    <label htmlFor="sms-alerts-toggle">SMS alerts</label>
                    <input
                      id="sms-alerts-toggle"
                      type="checkbox"
                      checked={editorSettings?.sms_alerts_enabled ?? false}
                      onChange={() =>
                        void handleInstantToggleUpdate("sms_alerts_enabled")
                      }
                      disabled={
                        !editorSettings || settingsPendingField !== null
                      }
                    />
                  </div>
                  {settingsPendingField !== null && (
                    <div className="metric-note">Saving changes...</div>
                  )}
                  {(editorSettings?.warnings?.length ?? 0) > 0 && (
                    <div className="alert">
                      {editorSettings?.warnings.map((warning) => warning).join(" ")}
                    </div>
                  )}
                </>
              )}
            </section>
          )}
        </aside>
      </section>
    </div>
  );
};

export default DashboardPage;
