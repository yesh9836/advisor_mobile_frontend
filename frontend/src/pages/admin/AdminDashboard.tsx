import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getAuditLogs, getDashboardStats } from "@/api/admin";
import type { AuditLog, DashboardStats } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";
import { isRequestCanceled, useLatestRequest } from "@/utils/request-control";

const formatCurrency = (amountCents: number, currency: string): string => {
  return (amountCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatTimestamp = (isoTimestamp: string): string => {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) {
    return isoTimestamp;
  }

  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};

const formatActionLabel = (value: string): string =>
  value.replace(/_/g, " ").trim().toUpperCase();

const formatActorLabel = (entry: AuditLog): string | null => {
  const actorParts = [entry.actor_name, entry.actor_email].filter(
    (value): value is string => typeof value === "string" && value.trim().length > 0,
  );

  if (actorParts.length > 0) {
    return actorParts.join(" • ");
  }

  if (entry.actor_user_id !== null) {
    return `User #${entry.actor_user_id}`;
  }

  return null;
};

const ACTIVITY_PREVIEW_LIMIT = 5;

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [recentActivity, setRecentActivity] = useState<AuditLog[]>([]);
  const [showAllRecentActivity, setShowAllRecentActivity] = useState(false);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityError, setActivityError] = useState<string | null>(null);
  const { beginRequest, isLatestRequest } = useLatestRequest();

  useEffect(() => {
    const { requestId, signal } = beginRequest();

    const loadDashboard = async () => {
      const [statsResult, activityResult] = await Promise.allSettled([
        getDashboardStats({ signal }),
        getAuditLogs({}, 1, 20, { signal }),
      ]);

      if (!isLatestRequest(requestId)) {
        return;
      }

      if (statsResult.status === "fulfilled") {
        setStats(statsResult.value);
      } else if (!isRequestCanceled(statsResult.reason)) {
        setStats(null);
        setStatsError(
          getApiErrorMessage(
            statsResult.reason,
            "Unable to load admin dashboard.",
          ),
        );
      }
      setStatsLoading(false);

      if (activityResult.status === "fulfilled") {
        setRecentActivity(activityResult.value.items);
        setShowAllRecentActivity(false);
      } else if (!isRequestCanceled(activityResult.reason)) {
        setRecentActivity([]);
        setShowAllRecentActivity(false);
        setActivityError(
          getApiErrorMessage(
            activityResult.reason,
            "Unable to load recent activity.",
          ),
        );
      }
      setActivityLoading(false);
    };

    void loadDashboard();
  }, [beginRequest, isLatestRequest]);

  const visibleRecentActivity = useMemo(() => {
    return showAllRecentActivity
      ? recentActivity
      : recentActivity.slice(0, ACTIVITY_PREVIEW_LIMIT);
  }, [recentActivity, showAllRecentActivity]);

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin Dashboard</h1>
          <p className="page-subtitle">
            Monitor platform health and jump into inventory, orders, imports, and license reviews.
          </p>
        </div>
      </div>

      {statsError && <div className="alert">{statsError}</div>}
      {activityError && <div className="alert">{activityError}</div>}

      <section className="grid-3">
        <article className="panel">
          <div className="metric-title">Total Users</div>
          <div className="metric-value">{statsLoading ? "..." : stats?.total_users ?? 0}</div>
          <div className="metric-note">Admin + advisor accounts</div>
        </article>

        <article className="panel">
          <div className="metric-title">Completed Purchases</div>
          <div className="metric-value">
            {statsLoading ? "..." : stats?.completed_purchases ?? 0}
          </div>
          <div className="metric-note">Paid package checkouts</div>
        </article>

        <article className="panel">
          <div className="metric-title">Advisors With Credits</div>
          <div className="metric-value">
            {statsLoading ? "..." : stats?.advisors_with_credits ?? 0}
          </div>
          <div className="metric-note">Advisors able to download now</div>
        </article>

        <article className="panel">
          <div className="metric-title">Revenue</div>
          <div className="metric-value">
            {statsLoading
              ? "..."
              : formatCurrency(
                  stats?.total_revenue_cents ?? 0,
                  stats?.currency ?? "USD",
                )}
          </div>
          <div className="metric-note">From completed purchases</div>
        </article>
      </section>

      <section className="grid-main">
        <article className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Admin Workflows</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Navigate operational flows for lead inventory, order monitoring, and imports.
            </p>
          </div>

          <div className="row" style={{ flexWrap: "wrap" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate("/admin/lead-inventory")}
            >
              Lead Inventory
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/orders")}
            >
              Orders
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/users")}
            >
              Users
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/imports")}
            >
              Imports
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/license-reviews")}
            >
              License Reviews
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/analytics")}
            >
              Analytics
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/admin/plans")}
            >
              Plans
            </button>
          </div>
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Queue Snapshot</h2>
          </div>
          <div style={{ color: "#334155" }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                gap: 8,
              }}
            >
              <button
                type="button"
                onClick={() => navigate("/admin/license-reviews")}
                className="btn btn-secondary"
                style={{ padding: "4px 10px", fontSize: 12 }}
              >
                Pending approvals
              </button>
              <strong>{statsLoading ? "..." : stats?.pending_licenses ?? 0}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
              <span>Total leads</span>
              <strong>{statsLoading ? "..." : stats?.total_leads ?? 0}</strong>
            </div>
          </div>
        </aside>
      </section>

      <section className="panel stack">
        <div className="page-header-row">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Recent Activity</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Latest audit events across admin and advisor actions.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate("/admin/imports")}
          >
            View Imports History
          </button>
        </div>

        {activityLoading && <p style={{ margin: 0, color: "#475569" }}>Loading recent activity...</p>}

        {!activityLoading && recentActivity.length === 0 && (
          <p style={{ margin: 0, color: "#475569" }}>No recent activity found.</p>
        )}

        {!activityLoading && recentActivity.length > 0 && (
          <div className="stack">
            {visibleRecentActivity.map((entry) => {
              const actorLabel = formatActorLabel(entry);

              return (
                <section
                  key={entry.id}
                  className="panel"
                  style={{ background: "#f8fafc" }}
                >
                  <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ color: "#0b1b49", fontWeight: 700 }}>
                      {formatActionLabel(entry.action)}
                    </div>
                    <div style={{ color: "#64748b", fontSize: 13 }}>
                      {formatTimestamp(entry.created_at)}
                    </div>
                  </div>
                  <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
                    {entry.entity_type}
                    {entry.entity_id !== null ? ` #${entry.entity_id}` : ""}
                  </p>
                  {actorLabel && (
                    <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
                      Performed by: {actorLabel}
                    </p>
                  )}
                </section>
              );
            })}

            {recentActivity.length > ACTIVITY_PREVIEW_LIMIT && (
              <button
                type="button"
                className="btn btn-secondary"
                style={{ alignSelf: "flex-start" }}
                onClick={() => setShowAllRecentActivity((current) => !current)}
              >
                {showAllRecentActivity
                  ? "Show Less Recent Activity"
                  : `Show Remaining Recent Activity (${
                      recentActivity.length - ACTIVITY_PREVIEW_LIMIT
                    })`}
              </button>
            )}
          </div>
        )}
      </section>
    </div>
  );
};

export default AdminDashboard;
