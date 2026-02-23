import type { CSSProperties } from "react";
import { useEffect, useState } from "react";

import { downloadOrdersExport, getOrders } from "@/api/admin";
import type { AdminOrderListItem } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const formatOrderTimestamp = (isoTimestamp: string): string => {
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

const formatStatusLabel = (status: string): string =>
  status
    .replace(/_/g, " ")
    .trim()
    .toUpperCase();

const badgeStyle = (status: string): CSSProperties => {
  const normalizedStatus = status.toLowerCase();

  if (normalizedStatus === "completed") {
    return {
      border: "1px solid #bfdbfe",
      background: "#eff6ff",
      color: "#1d4ed8",
    };
  }

  if (normalizedStatus === "pending") {
    return {
      border: "1px solid #fde68a",
      background: "#fffbeb",
      color: "#b45309",
    };
  }

  if (["failed", "refunded", "canceled"].includes(normalizedStatus)) {
    return {
      border: "1px solid #fecaca",
      background: "#fef2f2",
      color: "#b91c1c",
    };
  }

  return {
    border: "1px solid #dbeafe",
    background: "#f8fafc",
    color: "#334155",
  };
};

const OrdersPage = () => {
  const [orders, setOrders] = useState<AdminOrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadOrders = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getOrders(1, 20);
        if (cancelled) return;
        setOrders(response.items);
      } catch (loadError) {
        if (cancelled) return;
        setOrders([]);
        setError(getApiErrorMessage(loadError, "Unable to load recent orders."));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadOrders();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const { blob, filename } = await downloadOrdersExport();
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(objectUrl);
    } catch (exportError) {
      setError(getApiErrorMessage(exportError, "Unable to export orders CSV."));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="page">
      <div>
        <h1>Admin • Orders</h1>
        <p className="page-subtitle">Monitor payments, fulfillment, and notifications.</p>
      </div>

      {error && <div className="alert">{error}</div>}

      <section className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <div
          className="page-header-row"
          style={{
            padding: 16,
            borderBottom: "1px solid #e2e8f0",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Recent Orders</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Stripe checkout + webhook fulfillment status.
            </p>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void handleExport()}
            disabled={loading || exporting || orders.length === 0}
          >
            {exporting ? "Exporting..." : "Export"}
          </button>
        </div>

        {loading && (
          <div style={{ padding: 16, color: "#475569" }}>
            Loading orders...
          </div>
        )}

        {!loading && orders.length === 0 && (
          <div style={{ padding: 16, color: "#475569" }}>
            No orders yet.
          </div>
        )}

        {!loading && orders.map((order) => (
          <div
            key={order.id}
            style={{
              borderBottom: "1px solid #e2e8f0",
              padding: 16,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
            }}
          >
            <div>
              <div style={{ fontSize: 18, color: "#0b1b49", fontWeight: 700 }}>
                {order.advisor_name} • {order.package_name ?? "Unknown Plan"}
                {order.quantity !== null ? ` (${order.quantity})` : ""}
              </div>
              <div style={{ marginTop: 4, color: "#475569" }}>
                {order.order_reference} • {formatOrderTimestamp(order.created_at)}
              </div>
              <div style={{ marginTop: 4, color: "#475569" }}>
                {(order.amount_cents / 100).toLocaleString("en-US", {
                  style: "currency",
                  currency: (order.currency || "USD").toUpperCase(),
                })}{" "}
                • remaining credits {order.remaining_credits ?? 0}
              </div>
            </div>

            <span
              style={{
                borderRadius: 999,
                padding: "4px 12px",
                fontSize: 14,
                fontWeight: 700,
                ...badgeStyle(order.status),
              }}
            >
              {formatStatusLabel(order.status)}
            </span>
          </div>
        ))}
      </section>
    </div>
  );
};

export default OrdersPage;
