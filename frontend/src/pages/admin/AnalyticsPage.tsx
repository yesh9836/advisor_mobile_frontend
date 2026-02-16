import { useEffect, useMemo, useState } from "react";

import { getAnalyticsOverview } from "@/api/admin";
import type {
  AdminAnalyticsOverview,
  MonthlyRevenuePoint,
  PlanBreakdownItem,
  StateDistributionItem,
  UserGrowthPoint,
} from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const formatMonthLabel = (value: string): string => {
  const [year, month] = value.split("-");
  const yearNumber = Number(year);
  const monthNumber = Number(month);
  if (
    Number.isNaN(yearNumber) ||
    Number.isNaN(monthNumber) ||
    monthNumber < 1 ||
    monthNumber > 12
  ) {
    return value;
  }

  const date = new Date(Date.UTC(yearNumber, monthNumber - 1, 1));
  return date.toLocaleString("en-US", { month: "short", year: "numeric" });
};

const formatCurrency = (amountCents: number): string =>
  (amountCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });

const EmptyChart = ({ message }: { message: string }) => (
  <div
    style={{
      border: "1px dashed #cbd5e1",
      borderRadius: 12,
      padding: 16,
      color: "#475569",
      fontSize: 14,
      background: "#f8fafc",
    }}
  >
    {message}
  </div>
);

const RevenueTrendChart = ({ data }: { data: MonthlyRevenuePoint[] }) => {
  if (data.length === 0) {
    return <EmptyChart message="No monthly revenue data yet." />;
  }

  const width = 640;
  const height = 220;
  const padding = 28;
  const maxRevenue = Math.max(...data.map((item) => item.revenue_cents), 1);
  const stepX = data.length > 1 ? (width - padding * 2) / (data.length - 1) : 0;

  const points = data.map((point, index) => {
    const x = padding + index * stepX;
    const y =
      height -
      padding -
      (point.revenue_cents / maxRevenue) * (height - padding * 2);
    return { x, y, point };
  });

  const polyline = points.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="stack">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Monthly revenue trend chart"
        style={{ width: "100%", border: "1px solid #dbe4f0", borderRadius: 12, background: "#fff" }}
      >
        <line
          x1={padding}
          y1={height - padding}
          x2={width - padding}
          y2={height - padding}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        <line
          x1={padding}
          y1={padding}
          x2={padding}
          y2={height - padding}
          stroke="#cbd5e1"
          strokeWidth={1}
        />
        <polyline
          points={polyline}
          fill="none"
          stroke="#0b1b49"
          strokeWidth={3}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map((entry) => (
          <circle
            key={entry.point.month}
            cx={entry.x}
            cy={entry.y}
            r={4}
            fill="#0b1b49"
          />
        ))}
      </svg>

      <div className="row" style={{ flexWrap: "wrap", rowGap: 10 }}>
        {data.map((point) => (
          <div
            key={point.month}
            style={{
              border: "1px solid #dbe4f0",
              borderRadius: 999,
              padding: "4px 10px",
              color: "#334155",
              fontSize: 12,
            }}
          >
            {formatMonthLabel(point.month)}: {formatCurrency(point.revenue_cents)}
          </div>
        ))}
      </div>
    </div>
  );
};

const HorizontalBarChart = ({
  data,
  valueLabel,
  emptyMessage,
  barColor,
  ariaLabel,
  totalCountLabel,
}: {
  data: Array<{ key: string; label: string; value: number; secondary?: string }>;
  valueLabel: (value: number) => string;
  emptyMessage: string;
  barColor: string;
  ariaLabel: string;
  totalCountLabel: string;
}) => {
  if (data.length === 0) {
    return <EmptyChart message={emptyMessage} />;
  }

  const maxValue = Math.max(...data.map((item) => item.value), 1);

  return (
    <div className="stack" role="img" aria-label={ariaLabel}>
      <div style={{ color: "#475569", fontSize: 13 }}>{totalCountLabel}</div>
      {data.map((item) => {
        const widthPct = Math.max(4, (item.value / maxValue) * 100);

        return (
          <div key={item.key} className="stack" style={{ gap: 4 }}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
              <strong style={{ color: "#0b1b49" }}>{item.label}</strong>
              <span style={{ color: "#334155", fontSize: 13 }}>{valueLabel(item.value)}</span>
            </div>
            {item.secondary && (
              <div style={{ color: "#64748b", fontSize: 12 }}>{item.secondary}</div>
            )}
            <div
              style={{
                height: 10,
                borderRadius: 999,
                background: "#e2e8f0",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${widthPct}%`,
                  height: "100%",
                  background: barColor,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

const UserGrowthChart = ({ data }: { data: UserGrowthPoint[] }) => {
  if (data.length === 0) {
    return <EmptyChart message="No advisor growth data yet." />;
  }

  const maxValue = Math.max(...data.map((item) => item.new_users), 1);

  return (
    <div className="stack" role="img" aria-label="Advisor user growth chart">
      {data.map((item) => {
        const widthPct = Math.max(4, (item.new_users / maxValue) * 100);
        return (
          <div key={item.month} className="stack" style={{ gap: 4 }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#0b1b49", fontWeight: 700 }}>
                {formatMonthLabel(item.month)}
              </span>
              <span style={{ color: "#334155", fontSize: 13 }}>
                {item.new_users} new advisors
              </span>
            </div>
            <div
              style={{
                height: 12,
                borderRadius: 999,
                background: "#e2e8f0",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${widthPct}%`,
                  height: "100%",
                  background: "#1d4ed8",
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

const AnalyticsPage = () => {
  const [data, setData] = useState<AdminAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadAnalytics = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getAnalyticsOverview();
        if (cancelled) return;
        setData(response);
      } catch (loadError) {
        if (cancelled) return;
        setData(null);
        setError(getApiErrorMessage(loadError, "Unable to load analytics."));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadAnalytics();

    return () => {
      cancelled = true;
    };
  }, []);

  const planBreakdownRows = useMemo(
    () =>
      (data?.plan_breakdown ?? []).map((item: PlanBreakdownItem) => ({
        key: item.package_name,
        label: item.package_name,
        value: item.purchases,
        secondary: `Revenue ${formatCurrency(item.revenue_cents)} • Remaining credits ${item.credits_remaining}`,
      })),
    [data?.plan_breakdown],
  );

  const stateDistributionRows = useMemo(
    () =>
      (data?.state_distribution ?? []).map((item: StateDistributionItem) => ({
        key: item.state_code,
        label: item.state_code,
        value: item.lead_count,
      })),
    [data?.state_distribution],
  );

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • Analytics</h1>
          <p className="page-subtitle">
            Revenue, package mix, lead distribution, and advisor growth trends.
          </p>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
      {loading && <section className="panel">Loading analytics...</section>}

      {!loading && (
        <>
          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Monthly Revenue</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Revenue generated by completed package purchases per month.
              </p>
            </div>
            <RevenueTrendChart data={data?.monthly_revenue ?? []} />
          </section>

          <section className="grid-main">
            <article className="panel stack">
              <div>
                <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Package Breakdown</h2>
                <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                  Purchase distribution and credit usage by package.
                </p>
              </div>
              <HorizontalBarChart
                data={planBreakdownRows}
                valueLabel={(value) => `${value} purchases`}
                emptyMessage="No package breakdown data yet."
                barColor="#0b1b49"
                ariaLabel="Plan breakdown chart"
                totalCountLabel={`${planBreakdownRows.length} packages`}
              />
            </article>

            <article className="panel stack">
              <div>
                <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>User Growth</h2>
                <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                  New advisor signups over time.
                </p>
              </div>
              <UserGrowthChart data={data?.user_growth ?? []} />
            </article>
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Lead State Distribution</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Inventory footprint by state.
              </p>
            </div>
            <HorizontalBarChart
              data={stateDistributionRows}
              valueLabel={(value) => `${value} leads`}
              emptyMessage="No lead state distribution data yet."
              barColor="#1d4ed8"
              ariaLabel="Lead state distribution chart"
              totalCountLabel={`${stateDistributionRows.length} states`}
            />
          </section>
        </>
      )}
    </div>
  );
};

export default AnalyticsPage;
