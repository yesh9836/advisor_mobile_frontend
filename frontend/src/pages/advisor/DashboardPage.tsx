import axios from "axios";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getLeadDashboardSummary, getLeads } from "@/api/leads";
import type {
  Lead,
  LeadDashboardSummary,
  LeadOutcomeStatus,
} from "@/types/lead";

type LeadStage = "New" | "Contacted" | "Appointment Set";

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

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

const toDisplayStage = (
  status: LeadOutcomeStatus | null | undefined,
): LeadStage => {
  if (status === "contacted") return "Contacted";
  if (status === "appointment_set") return "Appointment Set";
  return "New";
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((issue) => issue.msg ?? "Validation error").join(", ");
    }
    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
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

const DashboardPage = () => {
  const navigate = useNavigate();

  const [recentLeads, setRecentLeads] = useState<RecentLeadItem[]>([]);
  const [summary, setSummary] = useState<LeadDashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
        setError(getErrorMessage(loadError, "Unable to load dashboard data."));
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, []);

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
              Read-only snapshot from account configuration.
            </p>
          </div>

          <section className="panel" style={{ padding: 12 }}>
            <h3 style={{ margin: 0, fontSize: 16, color: "#0b1b49" }}>
              Notifications
            </h3>
            <div style={{ marginTop: 8, color: "#334155" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>Email alerts</span>
                <strong>{settings?.email_alerts_enabled ? "On" : "Off"}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>SMS alerts</span>
                <strong>{settings?.sms_alerts_enabled ? "On" : "Off"}</strong>
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

          <button type="button" className="btn btn-primary" disabled>
            Edit Settings (Coming Soon)
          </button>
        </aside>
      </section>
    </div>
  );
};

export default DashboardPage;
