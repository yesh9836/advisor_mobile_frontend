import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDashboardStats } from "@/api/admin";
import type { DashboardStats } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const formatCurrency = (amountCents: number, currency: string): string => {
  return (amountCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: (currency || "USD").toUpperCase(),
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
};

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getDashboardStats();
        if (cancelled) return;
        setStats(response);
      } catch (loadError) {
        if (cancelled) return;
        setStats(null);
        setError(getApiErrorMessage(loadError, "Unable to load admin dashboard."));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadStats();

    return () => {
      cancelled = true;
    };
  }, []);

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

      {error && <div className="alert">{error}</div>}

      <section className="grid-3">
        <article className="panel">
          <div className="metric-title">Total Users</div>
          <div className="metric-value">{loading ? "..." : stats?.total_users ?? 0}</div>
          <div className="metric-note">Admin + advisor accounts</div>
        </article>

        <article className="panel">
          <div className="metric-title">Active Subscriptions</div>
          <div className="metric-value">
            {loading ? "..." : stats?.active_subscriptions ?? 0}
          </div>
          <div className="metric-note">Latest active plans</div>
        </article>

        <article className="panel">
          <div className="metric-title">Revenue</div>
          <div className="metric-value">
            {loading
              ? "..."
              : formatCurrency(
                  stats?.total_revenue_cents ?? 0,
                  stats?.currency ?? "USD",
                )}
          </div>
          <div className="metric-note">From active subscriptions</div>
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
          </div>
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Queue Snapshot</h2>
          </div>
          <div style={{ color: "#334155" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Pending licenses</span>
              <strong>{loading ? "..." : stats?.pending_licenses ?? 0}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Total leads</span>
              <strong>{loading ? "..." : stats?.total_leads ?? 0}</strong>
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
};

export default AdminDashboard;
