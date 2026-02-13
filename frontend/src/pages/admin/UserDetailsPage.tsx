import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { deactivateUser, getUser } from "@/api/admin";
import type {
  AuditLog,
  UserDetails,
  UserDownloadHistoryItem,
  UserLicenseItem,
  UserSubscriptionItem,
} from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const formatDateTime = (isoTimestamp: string | null): string => {
  if (!isoTimestamp) return "N/A";

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

const formatRole = (role: string): string =>
  role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();

const formatStatusLabel = (status: string): string =>
  status.replace(/_/g, " ").trim().toUpperCase();

const formatCurrency = (priceCents: number | null, currency: string | null): string => {
  if (priceCents === null || !currency) return "N/A";

  return (priceCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const userStatusBadgeStyle = (isActive: boolean): CSSProperties => {
  if (isActive) {
    return {
      border: "1px solid #bbf7d0",
      background: "#ecfdf3",
      color: "#047857",
    };
  }

  return {
    border: "1px solid #fecaca",
    background: "#fef2f2",
    color: "#b91c1c",
  };
};

const licenseStatusBadgeStyle = (status: string): CSSProperties => {
  const normalized = status.toLowerCase();

  if (normalized === "verified") {
    return {
      border: "1px solid #bbf7d0",
      background: "#ecfdf3",
      color: "#047857",
    };
  }

  if (normalized === "pending") {
    return {
      border: "1px solid #fde68a",
      background: "#fffbeb",
      color: "#b45309",
    };
  }

  return {
    border: "1px solid #fecaca",
    background: "#fef2f2",
    color: "#b91c1c",
  };
};

const renderSubscription = (subscription: UserSubscriptionItem | null) => {
  if (!subscription) {
    return <p style={{ color: "#475569", margin: 0 }}>No subscription found.</p>;
  }

  return (
    <div className="grid-3">
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Plan</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {subscription.plan_name ?? "Unknown plan"}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Status</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {formatStatusLabel(subscription.status)}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Price</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {formatCurrency(subscription.price_cents, subscription.currency)}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Current Period Start</div>
        <div style={{ color: "#334155" }}>
          {formatDateTime(subscription.current_period_start)}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Current Period End</div>
        <div style={{ color: "#334155" }}>
          {formatDateTime(subscription.current_period_end)}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Subscription Created</div>
        <div style={{ color: "#334155" }}>
          {formatDateTime(subscription.created_at)}
        </div>
      </div>
    </div>
  );
};

const renderLicense = (license: UserLicenseItem, index: number) => {
  return (
    <section
      key={license.id}
      className="panel"
      style={{
        background: index % 2 === 0 ? "#f8fafc" : "#ffffff",
      }}
    >
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0, fontSize: 22, color: "#0b1b49" }}>
          {license.state} • {license.license_number}
        </h3>
        <span
          style={{
            borderRadius: 999,
            padding: "3px 10px",
            fontSize: 12,
            fontWeight: 700,
            ...licenseStatusBadgeStyle(license.verification_status),
          }}
        >
          {formatStatusLabel(license.verification_status)}
        </span>
      </div>

      <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
        Type: {license.license_type ?? "N/A"} • Created: {formatDateTime(license.created_at)}
      </p>

      <p style={{ margin: "6px 0 0 0", color: "#475569" }}>
        Verified: {formatDateTime(license.verified_at)}
      </p>

      {license.rejection_reason && (
        <p style={{ margin: "8px 0 0 0", color: "#9f1239" }}>
          Rejection reason: {license.rejection_reason}
        </p>
      )}
    </section>
  );
};

const renderDownloadRow = (item: UserDownloadHistoryItem, index: number) => {
  return (
    <tr key={`${item.lead_id}-${item.downloaded_at}-${index}`} style={{ borderTop: "1px solid #e2e8f0" }}>
      <td style={{ padding: "10px 12px", color: "#0b1b49", fontWeight: 700 }}>{item.lead_id}</td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>{item.state_code}</td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>{formatDateTime(item.downloaded_at)}</td>
      <td style={{ padding: "10px 12px", color: "#475569" }}>{item.csv_batch_id ?? "N/A"}</td>
    </tr>
  );
};

const renderActivityRow = (item: AuditLog) => {
  const rawMeta = item.meta_data ? JSON.stringify(item.meta_data) : null;
  const metaPreview = rawMeta && rawMeta.length > 160 ? `${rawMeta.slice(0, 160)}...` : rawMeta;

  return (
    <section
      key={item.id}
      className="panel"
      style={{
        background: "#f8fafc",
      }}
    >
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {formatStatusLabel(item.action)}
        </div>
        <div style={{ color: "#64748b", fontSize: 13 }}>{formatDateTime(item.created_at)}</div>
      </div>

      <div style={{ marginTop: 8, color: "#334155", fontSize: 14 }}>
        Entity: {item.entity_type}
        {item.entity_id !== null ? ` #${item.entity_id}` : ""}
      </div>

      {item.ip_address && (
        <div style={{ marginTop: 6, color: "#475569", fontSize: 13 }}>IP: {item.ip_address}</div>
      )}

      {metaPreview && (
        <pre
          style={{
            marginTop: 8,
            background: "#f1f5f9",
            border: "1px solid #e2e8f0",
            borderRadius: 10,
            padding: 10,
            color: "#334155",
            fontSize: 12,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {metaPreview}
        </pre>
      )}
    </section>
  );
};

const UserDetailsPage = () => {
  const navigate = useNavigate();
  const { userId } = useParams<{ userId: string }>();

  const parsedUserId = useMemo(() => {
    if (!userId) return null;
    const parsed = Number(userId);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [userId]);

  const [details, setDetails] = useState<UserDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [deactivateReason, setDeactivateReason] = useState("");
  const [deactivateSubmitting, setDeactivateSubmitting] = useState(false);
  const [deactivateError, setDeactivateError] = useState<string | null>(null);
  const [deactivateSuccess, setDeactivateSuccess] = useState<string | null>(null);

  const loadDetails = useCallback(async () => {
    if (!parsedUserId) {
      setDetails(null);
      setError("Invalid user ID.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getUser(parsedUserId);
      setDetails(response);
    } catch (loadError) {
      setDetails(null);
      setError(getApiErrorMessage(loadError, "Unable to load user details."));
    } finally {
      setLoading(false);
    }
  }, [parsedUserId]);

  useEffect(() => {
    void loadDetails();
  }, [loadDetails]);

  const handleDeactivate = async () => {
    if (!parsedUserId || !details || !details.is_active) {
      return;
    }

    const confirmed = window.confirm(
      "Deactivate this user? They will no longer be able to authenticate.",
    );
    if (!confirmed) {
      return;
    }

    setDeactivateSubmitting(true);
    setDeactivateError(null);
    setDeactivateSuccess(null);

    try {
      await deactivateUser(parsedUserId, deactivateReason);
      setDeactivateSuccess("User deactivated successfully.");
      setDeactivateReason("");
      await loadDetails();
    } catch (submitError) {
      setDeactivateError(getApiErrorMessage(submitError, "Failed to deactivate user."));
    } finally {
      setDeactivateSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • User Details</h1>
          <p className="page-subtitle">
            Review user account, subscription, licenses, and recent platform activity.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => navigate("/admin/users")}
        >
          Back to Users
        </button>
      </div>

      {error && <div className="alert">{error}</div>}
      {deactivateError && <div className="alert">{deactivateError}</div>}
      {deactivateSuccess && <div className="success">{deactivateSuccess}</div>}

      {loading && <section className="panel">Loading user details...</section>}

      {!loading && details && (
        <>
          <section className="grid-main">
            <article className="panel stack">
              <div>
                <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>{details.name}</h2>
                <p style={{ margin: "4px 0 0 0", color: "#475569" }}>{details.email}</p>
              </div>

              <div className="row" style={{ flexWrap: "wrap", alignItems: "center" }}>
                <span style={{ color: "#334155" }}>Role: {formatRole(details.role)}</span>
                <span
                  style={{
                    borderRadius: 999,
                    padding: "3px 10px",
                    fontSize: 12,
                    fontWeight: 700,
                    ...userStatusBadgeStyle(details.is_active),
                  }}
                >
                  {details.is_active ? "ACTIVE" : "INACTIVE"}
                </span>
              </div>

              <div className="grid-3">
                <div>
                  <div style={{ color: "#64748b", fontSize: 13 }}>Created</div>
                  <div style={{ color: "#334155" }}>{formatDateTime(details.created_at)}</div>
                </div>
                <div>
                  <div style={{ color: "#64748b", fontSize: 13 }}>Deactivated At</div>
                  <div style={{ color: "#334155" }}>{formatDateTime(details.deactivated_at)}</div>
                </div>
                <div>
                  <div style={{ color: "#64748b", fontSize: 13 }}>Deactivated By</div>
                  <div style={{ color: "#334155" }}>
                    {details.deactivated_by === null ? "N/A" : details.deactivated_by}
                  </div>
                </div>
              </div>

              <div>
                <h3 style={{ margin: "4px 0 8px 0", fontSize: 24, color: "#0b1b49" }}>
                  Subscription
                </h3>
                {renderSubscription(details.subscription)}
              </div>
            </article>

            <aside className="panel stack">
              <div>
                <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Account Actions</h2>
              </div>

              <div className="field">
                <label htmlFor="deactivate-reason">Deactivation reason (optional)</label>
                <textarea
                  id="deactivate-reason"
                  value={deactivateReason}
                  onChange={(event) => setDeactivateReason(event.target.value)}
                  placeholder="Reason recorded in audit logs."
                  maxLength={500}
                  disabled={!details.is_active || deactivateSubmitting}
                />
              </div>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleDeactivate()}
                disabled={!details.is_active || deactivateSubmitting}
              >
                {details.is_active
                  ? deactivateSubmitting
                    ? "Deactivating..."
                    : "Deactivate User"
                  : "User Already Inactive"}
              </button>
            </aside>
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Licenses</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Latest submitted licenses and verification outcomes.
              </p>
            </div>

            {details.licenses.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No licenses found.</p>
            ) : (
              details.licenses.map((license, index) =>
                renderLicense(license as UserLicenseItem, index),
              )
            )}
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Download History</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Most recent lead downloads for this user (up to 100 records).
              </p>
            </div>

            {details.download_history.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No lead downloads recorded.</p>
            ) : (
              <div
                style={{
                  overflowX: "auto",
                  border: "1px solid #dbe4f0",
                  borderRadius: 12,
                }}
              >
                <table className="min-w-full bg-white text-left text-sm">
                  <thead style={{ background: "#f8fafc", color: "#1f3a6b" }}>
                    <tr>
                      <th style={{ padding: "10px 12px" }}>Lead ID</th>
                      <th style={{ padding: "10px 12px" }}>State</th>
                      <th style={{ padding: "10px 12px" }}>Downloaded At</th>
                      <th style={{ padding: "10px 12px" }}>Batch ID</th>
                    </tr>
                  </thead>
                  <tbody>{details.download_history.map(renderDownloadRow)}</tbody>
                </table>
              </div>
            )}
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Recent Activity</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Latest audit events initiated by this user (up to 100 records).
              </p>
            </div>

            {details.recent_activity.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No recent activity found.</p>
            ) : (
              details.recent_activity.map(renderActivityRow)
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default UserDetailsPage;
