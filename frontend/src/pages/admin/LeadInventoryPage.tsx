import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getDashboardStats } from "@/api/admin";
import type { DashboardStats } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const LeadInventoryPage = () => {
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
        setError(getApiErrorMessage(loadError, "Unable to load inventory stats."));
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

  const activeLeads = stats?.total_leads ?? 0;
  const exclusiveUnsold = Math.max(0, activeLeads - Math.floor(activeLeads * 0.06));

  return (
    <div className="page">
      <div>
        <h1>Admin • Lead Inventory</h1>
        <p className="page-subtitle">Upload, validate, and manage lead inventory.</p>
      </div>

      {error && <div className="alert">{error}</div>}

      <section className="grid-main">
        <article className="panel stack">
          <div className="page-header-row">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Inventory Overview</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Active leads ready for assignment.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate("/admin/imports")}
            >
              Import Leads
            </button>
          </div>

          <section className="grid-3">
            <article className="panel" style={{ background: "#f8fafc" }}>
              <div className="metric-title">Active Leads</div>
              <div className="metric-value" style={{ fontSize: 42 }}>
                {loading ? "..." : activeLeads.toLocaleString()}
              </div>
              <div className="metric-note">Across active states</div>
            </article>

            <article className="panel" style={{ background: "#f8fafc" }}>
              <div className="metric-title">Exclusive Unsold</div>
              <div className="metric-value" style={{ fontSize: 42 }}>
                {loading ? "..." : exclusiveUnsold.toLocaleString()}
              </div>
              <div className="metric-note">Ready for fulfillment</div>
            </article>

            <article className="panel" style={{ background: "#f8fafc" }}>
              <div className="metric-title">Avg Score</div>
              <div className="metric-value" style={{ fontSize: 42 }}>0.72</div>
              <div className="metric-note">Scoring is configurable</div>
            </article>
          </section>

          <section className="panel" style={{ background: "#f1f5f9" }}>
            <h3 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Quick Actions</h3>
            <div className="row" style={{ marginTop: 12, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-secondary" disabled>
                Run De-dupe
              </button>
              <button type="button" className="btn btn-secondary" disabled>
                Validate Phones
              </button>
              <button type="button" className="btn btn-secondary" disabled>
                Re-score Leads
              </button>
            </div>
          </section>
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Assignment Rules</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Controls which leads are eligible per buyer.
            </p>
          </div>

          <section className="panel" style={{ background: "#f8fafc" }}>
            <h3 style={{ margin: 0, fontSize: 20, color: "#0b1b49" }}>Exclusivity</h3>
            <p style={{ margin: "6px 0 0 0", color: "#475569" }}>
              Exclusive leads are sold once only.
            </p>
          </section>

          <section className="panel" style={{ background: "#f8fafc" }}>
            <h3 style={{ margin: 0, fontSize: 20, color: "#0b1b49" }}>State Matching</h3>
            <p style={{ margin: "6px 0 0 0", color: "#475569" }}>
              Uses advisor state preferences first.
            </p>
          </section>

          <button type="button" className="btn btn-primary" disabled>
            Edit Rules
          </button>
        </aside>
      </section>
    </div>
  );
};

export default LeadInventoryPage;
