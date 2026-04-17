import type { CSSProperties, Dispatch, SetStateAction } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  deactivateUser,
  getUser,
  getUserDownloadHistory,
  getUserLicenses,
  getUserPurchaseHistory,
  getUserRecentActivity,
} from "@/api/admin";
import type {
  AuditLog,
  UserCreditSummary,
  UserDetails,
  UserDownloadHistoryItem,
  UserHistoryPreview,
  UserLicenseItem,
  UserPurchaseItem,
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

const formatTitleLabel = (value: string): string =>
  value
    .replace(/_/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());

const formatCurrency = (priceCents: number, currency: string): string => {
  return (priceCents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

const formatActorLabel = (item: AuditLog): string | null => {
  const actorParts = [item.actor_name, item.actor_email].filter(
    (value): value is string => typeof value === "string" && value.trim().length > 0,
  );

  if (actorParts.length > 0) {
    return actorParts.join(" • ");
  }

  if (item.actor_user_id !== null) {
    return `User #${item.actor_user_id}`;
  }

  return null;
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

const HISTORY_PREVIEW_LIMIT = 5;
const HISTORY_PAGE_SIZE = 20;

interface HistorySectionState<TItem> {
  items: TItem[];
  total: number;
  page: number;
  isExpanded: boolean;
  isLoading: boolean;
  error: string | null;
}

interface PaginatedHistoryResponse<TItem> {
  items: TItem[];
  total: number;
  page: number;
  size: number;
}

const createEmptyHistorySectionState = <TItem,>(): HistorySectionState<TItem> => ({
  items: [],
  total: 0,
  page: 0,
  isExpanded: false,
  isLoading: false,
  error: null,
});

const createHistorySectionState = <TItem,>(
  preview: UserHistoryPreview<TItem>,
): HistorySectionState<TItem> => ({
  items: preview.items,
  total: preview.total,
  page: 0,
  isExpanded: false,
  isLoading: false,
  error: null,
});

const renderCreditSummary = (summary: UserCreditSummary) => {
  return (
    <div className="grid-3">
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Total Credits</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {summary.total_credits}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Remaining Credits</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {summary.remaining_credits}
        </div>
      </div>
      <div>
        <div style={{ color: "#64748b", fontSize: 13 }}>Completed Purchases</div>
        <div style={{ color: "#0b1b49", fontWeight: 700 }}>
          {summary.completed_purchases}
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

const getPurchaseRemainingPresentation = (
  purchase: UserPurchaseItem,
): {
  value: string;
  helper: string | null;
  color: string;
} => {
  const normalizedStatus = purchase.status.trim().toLowerCase();

  if (normalizedStatus === "completed") {
    return {
      value: String(purchase.credits_remaining),
      helper: null,
      color: "#334155",
    };
  }

  if (normalizedStatus === "pending") {
    return {
      value: "Not granted",
      helper: "Awaiting Stripe outcome",
      color: "#64748b",
    };
  }

  if (normalizedStatus === "canceled" || normalizedStatus === "failed" || normalizedStatus === "refunded") {
    return {
      value: "Not granted",
      helper: "No credits granted",
      color: "#64748b",
    };
  }

  return {
    value: "Not granted",
    helper: "Credits unavailable for this status",
    color: "#64748b",
  };
};

const renderPurchaseRow = (purchase: UserPurchaseItem, index: number) => {
  const remainingPresentation = getPurchaseRemainingPresentation(purchase);

  return (
    <tr
      key={`${purchase.id}-${index}`}
      style={{ borderTop: "1px solid #e2e8f0" }}
    >
      <td style={{ padding: "10px 12px", color: "#0b1b49", fontWeight: 700 }}>
        {purchase.order_reference}
      </td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>
        {purchase.package_name ?? "Unknown package"}
      </td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>
        {formatStatusLabel(purchase.status)}
      </td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>
        {formatCurrency(purchase.amount_cents, purchase.currency)}
      </td>
      <td style={{ padding: "10px 12px", color: "#334155" }}>
        {purchase.credits_total}
      </td>
      <td style={{ padding: "10px 12px", color: remainingPresentation.color }}>
        <div>{remainingPresentation.value}</div>
        {remainingPresentation.helper && (
          <div style={{ marginTop: 2, fontSize: 12, color: "#64748b" }}>
            {remainingPresentation.helper}
          </div>
        )}
      </td>
      <td style={{ padding: "10px 12px", color: "#475569" }}>
        {formatDateTime(purchase.purchased_at)}
      </td>
    </tr>
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

const getActivitySummary = (item: AuditLog): string => {
  const meta = item.meta_data ?? {};
  const state = typeof meta.state === "string" ? meta.state : null;
  const reason = typeof meta.reason === "string" ? meta.reason : null;
  const newStatus = typeof meta.new_status === "string" ? meta.new_status : null;
  const previousStatus = typeof meta.previous_status === "string" ? meta.previous_status : null;

  switch (item.action) {
    case "lead_downloaded":
      return state ? `Downloaded a lead in ${state}.` : "Downloaded a lead.";
    case "license_resubmitted":
      return state ? `Resubmitted a ${state} license for review.` : "Resubmitted a license for review.";
    case "lead_outcome_updated":
      if (previousStatus && newStatus) {
        return `Updated lead outcome from ${formatTitleLabel(previousStatus)} to ${formatTitleLabel(newStatus)}.`;
      }
      return "Updated a lead outcome.";
    case "delivery_settings_updated":
      return "Updated delivery preference settings.";
    case "purchase_initiated":
      return "Started a purchase checkout.";
    case "purchase_confirmed":
      return "Completed a purchase successfully.";
    case "purchase_credits_granted":
      return "Received purchase credits.";
    case "purchase_leads_allocated":
      return "Received lead allocations from a purchase.";
    case "purchase_credit_consumed":
      return "Used purchase credit for a lead.";
    case "user_deactivated":
      return reason ? `Deactivated a user account. Reason: ${reason}` : "Deactivated a user account.";
    default:
      return `Performed ${formatTitleLabel(item.action).toLowerCase()}.`;
  }
};

const getActivityDetails = (item: AuditLog): string[] => {
  const meta = item.meta_data;
  if (!meta) {
    return [];
  }

  const details: string[] = [];

  if (typeof meta.state === "string") {
    details.push(`State: ${meta.state}`);
  }
  if (typeof meta.status === "string") {
    details.push(`Status: ${formatTitleLabel(meta.status)}`);
  }
  if (typeof meta.reason === "string" && meta.reason.trim()) {
    details.push(`Reason: ${meta.reason.trim()}`);
  }
  if (typeof meta.lead_id === "number") {
    details.push(`Lead: #${meta.lead_id}`);
  }
  if (typeof meta.package_id === "number") {
    details.push(`Package: #${meta.package_id}`);
  }
  if (typeof meta.requested_count === "number") {
    details.push(`Requested: ${meta.requested_count}`);
  }
  if (typeof meta.assigned_count === "number") {
    details.push(`Assigned: ${meta.assigned_count}`);
  }
  if (typeof meta.unfulfilled_count === "number") {
    details.push(`Unfulfilled: ${meta.unfulfilled_count}`);
  }
  if (typeof meta.notes_changed === "boolean") {
    details.push(`Notes Changed: ${meta.notes_changed ? "Yes" : "No"}`);
  }
  if (typeof meta.previous_version === "number" && typeof meta.new_version === "number") {
    details.push(`Version: ${meta.previous_version} -> ${meta.new_version}`);
  }
  if (
    typeof meta.changed_fields === "object" &&
    meta.changed_fields !== null &&
    !Array.isArray(meta.changed_fields)
  ) {
    const changedFields = Object.keys(meta.changed_fields).slice(0, 3);
    if (changedFields.length > 0) {
      details.push(
        `Changed: ${changedFields.map((field) => formatTitleLabel(field)).join(", ")}`,
      );
    }
  }

  return details.slice(0, 4);
};

const renderActivityRow = (item: AuditLog) => {
  const summary = getActivitySummary(item);
  const details = getActivityDetails(item);
  const actorLabel = formatActorLabel(item);

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
          {formatTitleLabel(item.action)}
        </div>
        <div style={{ color: "#64748b", fontSize: 13 }}>{formatDateTime(item.created_at)}</div>
      </div>

      <div style={{ marginTop: 8, color: "#334155", fontSize: 14 }}>
        Affected: {formatTitleLabel(item.entity_type)}
        {item.entity_id !== null ? ` #${item.entity_id}` : ""}
      </div>

      {actorLabel && (
        <div style={{ marginTop: 8, color: "#334155", fontSize: 14 }}>
          Performed by: {actorLabel}
        </div>
      )}

      <p style={{ margin: "8px 0 0 0", color: "#475569", fontSize: 14 }}>{summary}</p>

      {details.length > 0 && (
        <div className="row" style={{ marginTop: 8, gap: 8, flexWrap: "wrap" }}>
          {details.map((detail) => (
            <span
              key={`${item.id}-${detail}`}
              style={{
                borderRadius: 999,
                padding: "4px 10px",
                fontSize: 12,
                fontWeight: 600,
                background: "#e2e8f0",
                color: "#334155",
              }}
            >
              {detail}
            </span>
          ))}
        </div>
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

  const [purchaseHistorySection, setPurchaseHistorySection] = useState<HistorySectionState<UserPurchaseItem>>(
    () => createEmptyHistorySectionState<UserPurchaseItem>(),
  );
  const [licensesSection, setLicensesSection] = useState<HistorySectionState<UserLicenseItem>>(
    () => createEmptyHistorySectionState<UserLicenseItem>(),
  );
  const [downloadHistorySection, setDownloadHistorySection] = useState<
    HistorySectionState<UserDownloadHistoryItem>
  >(() => createEmptyHistorySectionState<UserDownloadHistoryItem>());
  const [recentActivitySection, setRecentActivitySection] = useState<HistorySectionState<AuditLog>>(
    () => createEmptyHistorySectionState<AuditLog>(),
  );

  const loadDetails = useCallback(async () => {
    if (!parsedUserId) {
      setDetails(null);
      setPurchaseHistorySection(createEmptyHistorySectionState<UserPurchaseItem>());
      setLicensesSection(createEmptyHistorySectionState<UserLicenseItem>());
      setDownloadHistorySection(createEmptyHistorySectionState<UserDownloadHistoryItem>());
      setRecentActivitySection(createEmptyHistorySectionState<AuditLog>());
      setError("Invalid user ID.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await getUser(parsedUserId);
      setDetails(response);
      setLicensesSection(createHistorySectionState(response.licenses_preview));
      setPurchaseHistorySection(createHistorySectionState(response.purchase_history_preview));
      setDownloadHistorySection(createHistorySectionState(response.download_history_preview));
      setRecentActivitySection(createHistorySectionState(response.recent_activity_preview));
    } catch (loadError) {
      setDetails(null);
      setLicensesSection(createEmptyHistorySectionState<UserLicenseItem>());
      setPurchaseHistorySection(createEmptyHistorySectionState<UserPurchaseItem>());
      setDownloadHistorySection(createEmptyHistorySectionState<UserDownloadHistoryItem>());
      setRecentActivitySection(createEmptyHistorySectionState<AuditLog>());
      setError(getApiErrorMessage(loadError, "Unable to load user details."));
    } finally {
      setLoading(false);
    }
  }, [parsedUserId]);

  useEffect(() => {
    void loadDetails();
  }, [loadDetails]);

  async function loadHistoryPage<TItem>(
    params: {
      sectionLabel: string;
      currentPage: number;
      setSection: Dispatch<SetStateAction<HistorySectionState<TItem>>>;
      fetchPage: (
        userId: number,
        page: number,
        size: number,
      ) => Promise<PaginatedHistoryResponse<TItem>>;
      append: boolean;
    },
  ): Promise<void> {
    if (!parsedUserId) {
      return;
    }

    const nextPage = params.append ? params.currentPage + 1 : 1;

    params.setSection((current) => ({
      ...current,
      isExpanded: true,
      isLoading: true,
      error: null,
    }));

    try {
      const response = await params.fetchPage(parsedUserId, nextPage, HISTORY_PAGE_SIZE);
      params.setSection((current) => ({
        ...current,
        items: params.append ? [...current.items, ...response.items] : response.items,
        total: response.total,
        page: response.page,
        isExpanded: true,
        isLoading: false,
        error: null,
      }));
    } catch (loadError) {
      params.setSection((current) => ({
        ...current,
        isLoading: false,
        error: getApiErrorMessage(loadError, `Unable to load ${params.sectionLabel}.`),
      }));
    }
  }

  async function toggleHistorySection<TItem>(
    params: {
      sectionLabel: string;
      state: HistorySectionState<TItem>;
      setSection: Dispatch<SetStateAction<HistorySectionState<TItem>>>;
      fetchPage: (
        userId: number,
        page: number,
        size: number,
      ) => Promise<PaginatedHistoryResponse<TItem>>;
    },
  ): Promise<void> {
    if (params.state.isExpanded) {
      params.setSection((current) => ({
        ...current,
        isExpanded: false,
        error: null,
      }));
      return;
    }

    if (params.state.page === 0 && params.state.total > HISTORY_PREVIEW_LIMIT) {
      await loadHistoryPage({
        sectionLabel: params.sectionLabel,
        currentPage: 0,
        setSection: params.setSection,
        fetchPage: params.fetchPage,
        append: false,
      });
      return;
    }

    params.setSection((current) => ({
      ...current,
      isExpanded: true,
      error: null,
    }));
  }

  async function loadMoreHistorySection<TItem>(
    params: {
      sectionLabel: string;
      state: HistorySectionState<TItem>;
      setSection: Dispatch<SetStateAction<HistorySectionState<TItem>>>;
      fetchPage: (
        userId: number,
        page: number,
        size: number,
      ) => Promise<PaginatedHistoryResponse<TItem>>;
    },
  ): Promise<void> {
    if (params.state.isLoading || params.state.items.length >= params.state.total) {
      return;
    }

    await loadHistoryPage({
      sectionLabel: params.sectionLabel,
      currentPage: params.state.page,
      setSection: params.setSection,
      fetchPage: params.fetchPage,
      append: true,
    });
  }

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

  const visiblePurchaseHistory = purchaseHistorySection.isExpanded
    ? purchaseHistorySection.items
    : purchaseHistorySection.items.slice(0, HISTORY_PREVIEW_LIMIT);
  const visibleLicenses = licensesSection.isExpanded
    ? licensesSection.items
    : licensesSection.items.slice(0, HISTORY_PREVIEW_LIMIT);
  const visibleDownloadHistory = downloadHistorySection.isExpanded
    ? downloadHistorySection.items
    : downloadHistorySection.items.slice(0, HISTORY_PREVIEW_LIMIT);
  const visibleRecentActivity = recentActivitySection.isExpanded
    ? recentActivitySection.items
    : recentActivitySection.items.slice(0, HISTORY_PREVIEW_LIMIT);

  const purchaseHistoryHasMore = purchaseHistorySection.total > HISTORY_PREVIEW_LIMIT;
  const licensesHasMore = licensesSection.total > HISTORY_PREVIEW_LIMIT;
  const downloadHistoryHasMore = downloadHistorySection.total > HISTORY_PREVIEW_LIMIT;
  const recentActivityHasMore = recentActivitySection.total > HISTORY_PREVIEW_LIMIT;

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • User Details</h1>
          <p className="page-subtitle">
            Review user account, purchases, licenses, and recent platform activity.
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
                  Credit Summary
                </h3>
                {renderCreditSummary(details.credit_summary)}
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
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Purchase History</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Showing the latest 5 purchases first. Load fuller history on demand.
              </p>
            </div>

            {purchaseHistorySection.error && <div className="alert">{purchaseHistorySection.error}</div>}

            {visiblePurchaseHistory.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No purchases found.</p>
            ) : (
              <>
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
                        <th style={{ padding: "10px 12px" }}>Order</th>
                        <th style={{ padding: "10px 12px" }}>Package</th>
                        <th style={{ padding: "10px 12px" }}>Status</th>
                        <th style={{ padding: "10px 12px" }}>Amount</th>
                        <th style={{ padding: "10px 12px" }}>Package Credits</th>
                        <th style={{ padding: "10px 12px" }}>Usable Remaining</th>
                        <th style={{ padding: "10px 12px" }}>Purchased At</th>
                      </tr>
                    </thead>
                    <tbody>{visiblePurchaseHistory.map(renderPurchaseRow)}</tbody>
                  </table>
                </div>

                {purchaseHistorySection.isExpanded && (
                  <p style={{ margin: 0, color: "#475569" }}>
                    Showing {purchaseHistorySection.items.length} of {purchaseHistorySection.total} purchase records.
                  </p>
                )}

                {purchaseHistoryHasMore && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() =>
                        void toggleHistorySection({
                          sectionLabel: "purchase history",
                          state: purchaseHistorySection,
                          setSection: setPurchaseHistorySection,
                          fetchPage: getUserPurchaseHistory,
                        })
                      }
                      disabled={purchaseHistorySection.isLoading}
                    >
                      {purchaseHistorySection.isExpanded
                        ? "Show Less Purchase History"
                        : purchaseHistorySection.isLoading
                          ? "Loading Purchase History..."
                          : `View Full Purchase History (${
                              purchaseHistorySection.total - HISTORY_PREVIEW_LIMIT
                            } more)`}
                    </button>

                    {purchaseHistorySection.isExpanded &&
                      purchaseHistorySection.items.length < purchaseHistorySection.total && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() =>
                            void loadMoreHistorySection({
                              sectionLabel: "purchase history",
                              state: purchaseHistorySection,
                              setSection: setPurchaseHistorySection,
                              fetchPage: getUserPurchaseHistory,
                            })
                          }
                          disabled={purchaseHistorySection.isLoading}
                        >
                          {purchaseHistorySection.isLoading ? "Loading..." : "Load More Purchases"}
                        </button>
                      )}
                  </div>
                )}
              </>
            )}
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Licenses</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Showing the latest 5 licenses first. Load fuller history on demand.
              </p>
            </div>

            {licensesSection.error && <div className="alert">{licensesSection.error}</div>}

            {visibleLicenses.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No licenses found.</p>
            ) : (
              <>
                {visibleLicenses.map((license, index) => renderLicense(license, index))}

                {licensesSection.isExpanded && (
                  <p style={{ margin: 0, color: "#475569" }}>
                    Showing {licensesSection.items.length} of {licensesSection.total} license records.
                  </p>
                )}

                {licensesHasMore && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() =>
                        void toggleHistorySection({
                          sectionLabel: "licenses",
                          state: licensesSection,
                          setSection: setLicensesSection,
                          fetchPage: getUserLicenses,
                        })
                      }
                      disabled={licensesSection.isLoading}
                    >
                      {licensesSection.isExpanded
                        ? "Show Less Licenses"
                        : licensesSection.isLoading
                          ? "Loading Licenses..."
                          : `View Full Licenses (${licensesSection.total - HISTORY_PREVIEW_LIMIT} more)`}
                    </button>

                    {licensesSection.isExpanded &&
                      licensesSection.items.length < licensesSection.total && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() =>
                            void loadMoreHistorySection({
                              sectionLabel: "licenses",
                              state: licensesSection,
                              setSection: setLicensesSection,
                              fetchPage: getUserLicenses,
                            })
                          }
                          disabled={licensesSection.isLoading}
                        >
                          {licensesSection.isLoading ? "Loading..." : "Load More Licenses"}
                        </button>
                      )}
                  </div>
                )}
              </>
            )}
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Download History</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Showing the latest 5 downloads first. Load fuller history on demand.
              </p>
            </div>

            {downloadHistorySection.error && <div className="alert">{downloadHistorySection.error}</div>}

            {visibleDownloadHistory.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No lead downloads recorded.</p>
            ) : (
              <>
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
                    <tbody>{visibleDownloadHistory.map(renderDownloadRow)}</tbody>
                  </table>
                </div>

                {downloadHistorySection.isExpanded && (
                  <p style={{ margin: 0, color: "#475569" }}>
                    Showing {downloadHistorySection.items.length} of {downloadHistorySection.total} download records.
                  </p>
                )}

                {downloadHistoryHasMore && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() =>
                        void toggleHistorySection({
                          sectionLabel: "download history",
                          state: downloadHistorySection,
                          setSection: setDownloadHistorySection,
                          fetchPage: getUserDownloadHistory,
                        })
                      }
                      disabled={downloadHistorySection.isLoading}
                    >
                      {downloadHistorySection.isExpanded
                        ? "Show Less Download History"
                        : downloadHistorySection.isLoading
                          ? "Loading Download History..."
                          : `View Full Download History (${
                              downloadHistorySection.total - HISTORY_PREVIEW_LIMIT
                            } more)`}
                    </button>

                    {downloadHistorySection.isExpanded &&
                      downloadHistorySection.items.length < downloadHistorySection.total && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() =>
                            void loadMoreHistorySection({
                              sectionLabel: "download history",
                              state: downloadHistorySection,
                              setSection: setDownloadHistorySection,
                              fetchPage: getUserDownloadHistory,
                            })
                          }
                          disabled={downloadHistorySection.isLoading}
                        >
                          {downloadHistorySection.isLoading ? "Loading..." : "Load More Downloads"}
                        </button>
                      )}
                  </div>
                )}
              </>
            )}
          </section>

          <section className="panel stack">
            <div>
              <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Recent Activity</h2>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Showing the latest 5 audit events first. Load fuller history on demand.
              </p>
            </div>

            {recentActivitySection.error && <div className="alert">{recentActivitySection.error}</div>}

            {visibleRecentActivity.length === 0 ? (
              <p style={{ color: "#475569", margin: 0 }}>No recent activity found.</p>
            ) : (
              <>
                {visibleRecentActivity.map(renderActivityRow)}

                {recentActivitySection.isExpanded && (
                  <p style={{ margin: 0, color: "#475569" }}>
                    Showing {recentActivitySection.items.length} of {recentActivitySection.total} activity records.
                  </p>
                )}

                {recentActivityHasMore && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() =>
                        void toggleHistorySection({
                          sectionLabel: "recent activity",
                          state: recentActivitySection,
                          setSection: setRecentActivitySection,
                          fetchPage: getUserRecentActivity,
                        })
                      }
                      disabled={recentActivitySection.isLoading}
                    >
                      {recentActivitySection.isExpanded
                        ? "Show Less Recent Activity"
                        : recentActivitySection.isLoading
                          ? "Loading Recent Activity..."
                          : `View Full Recent Activity (${
                              recentActivitySection.total - HISTORY_PREVIEW_LIMIT
                            } more)`}
                    </button>

                    {recentActivitySection.isExpanded &&
                      recentActivitySection.items.length < recentActivitySection.total && (
                        <button
                          type="button"
                          className="btn btn-secondary"
                          onClick={() =>
                            void loadMoreHistorySection({
                              sectionLabel: "recent activity",
                              state: recentActivitySection,
                              setSection: setRecentActivitySection,
                              fetchPage: getUserRecentActivity,
                            })
                          }
                          disabled={recentActivitySection.isLoading}
                        >
                          {recentActivitySection.isLoading ? "Loading..." : "Load More Activity"}
                        </button>
                      )}
                  </div>
                )}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
};

export default UserDetailsPage;
