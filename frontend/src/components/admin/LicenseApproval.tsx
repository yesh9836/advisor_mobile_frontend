import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import {
  approveLicense,
  downloadLicenseDocument,
  getPendingLicenses,
  getProcessedLicenses,
  rejectLicense,
} from "@/api/admin";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import Table, { type TableColumn } from "@/components/common/Table";
import type {
  AdminLicenseDecisionRow,
  License,
  LicenseWithUser,
} from "@/types/license";

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

type ActionType = "approve" | "reject" | "download";

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => item.msg ?? "Validation error").join(", ");
    }
    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return fallback;
};

const formatDateTime = (value: string | null): string => {
  if (!value) {
    return "Not available";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
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

const toProcessedRow = (
  pendingLicense: LicenseWithUser,
  decision: License,
): AdminLicenseDecisionRow => {
  const decisionStatus =
    decision.verification_status === "verified" ? "verified" : "rejected";
  const fallbackDecisionAt = new Date().toISOString();
  const decisionAt =
    decisionStatus === "verified"
      ? decision.verified_at ?? fallbackDecisionAt
      : fallbackDecisionAt;

  return {
    license_id: pendingLicense.id,
    user_id: pendingLicense.user_id,
    user_name: pendingLicense.user_name,
    user_email: pendingLicense.user_email,
    state: pendingLicense.state,
    license_number: pendingLicense.license_number,
    license_type: decision.license_type,
    decision_status: decisionStatus,
    decision_at: decisionAt,
    rejection_reason: decision.rejection_reason,
    created_at: decision.created_at,
  };
};

const LicenseApproval = () => {
  const [pendingLicenses, setPendingLicenses] = useState<LicenseWithUser[]>([]);
  const [processedLicenses, setProcessedLicenses] = useState<
    AdminLicenseDecisionRow[]
  >([]);
  const [loadingPending, setLoadingPending] = useState(true);
  const [loadingProcessed, setLoadingProcessed] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [openRejectId, setOpenRejectId] = useState<number | null>(null);
  const [rejectionReasons, setRejectionReasons] = useState<Record<number, string>>(
    {},
  );
  const [rejectionErrors, setRejectionErrors] = useState<Record<number, string>>(
    {},
  );
  const [inflightAction, setInflightAction] = useState<{
    licenseId: number;
    type: ActionType;
  } | null>(null);

  const refreshProcessedLicenses = useCallback(async () => {
    try {
      const processed = await getProcessedLicenses();
      setProcessedLicenses(processed);
    } catch (refreshError) {
      setError(
        getErrorMessage(refreshError, "Unable to refresh processed licenses."),
      );
    }
  }, []);

  const loadAdminTables = useCallback(async () => {
    setLoadingPending(true);
    setLoadingProcessed(true);
    setError(null);

    const [pendingResult, processedResult] = await Promise.allSettled([
      getPendingLicenses(),
      getProcessedLicenses(),
    ]);

    const loadErrors: string[] = [];

    if (pendingResult.status === "fulfilled") {
      setPendingLicenses(pendingResult.value);
    } else {
      setPendingLicenses([]);
      loadErrors.push(
        getErrorMessage(pendingResult.reason, "Unable to load pending licenses."),
      );
    }

    if (processedResult.status === "fulfilled") {
      setProcessedLicenses(processedResult.value);
    } else {
      setProcessedLicenses([]);
      loadErrors.push(
        getErrorMessage(
          processedResult.reason,
          "Unable to load processed licenses.",
        ),
      );
    }

    if (loadErrors.length > 0) {
      setError(loadErrors.join(" "));
    }

    setLoadingPending(false);
    setLoadingProcessed(false);
  }, []);

  useEffect(() => {
    void loadAdminTables();
  }, [loadAdminTables]);

  const isBusy = inflightAction !== null;

  const handleApprove = async (license: LicenseWithUser) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId: license.id, type: "approve" });

    try {
      const approved = await approveLicense(license.id);
      setPendingLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      setProcessedLicenses((previous) => [
        toProcessedRow(license, approved),
        ...previous.filter((item) => item.license_id !== license.id),
      ]);
      setNotice(`License approved for ${license.user_name}.`);
      if (openRejectId === license.id) {
        setOpenRejectId(null);
      }
      void refreshProcessedLicenses();
    } catch (approveError) {
      setError(getErrorMessage(approveError, "Unable to approve license."));
    } finally {
      setInflightAction(null);
    }
  };

  const handleRejectToggle = (licenseId: number) => {
    setNotice(null);
    setError(null);
    setOpenRejectId((previous) => (previous === licenseId ? null : licenseId));
    setRejectionErrors((previous) => {
      const next = { ...previous };
      delete next[licenseId];
      return next;
    });
  };

  const handleRejectReasonChange = (licenseId: number, value: string) => {
    setRejectionReasons((previous) => ({
      ...previous,
      [licenseId]: value,
    }));

    if (value.trim()) {
      setRejectionErrors((previous) => {
        const next = { ...previous };
        delete next[licenseId];
        return next;
      });
    }
  };

  const handleRejectConfirm = async (license: LicenseWithUser) => {
    const reason = rejectionReasons[license.id]?.trim() ?? "";

    if (!reason) {
      setRejectionErrors((previous) => ({
        ...previous,
        [license.id]: "Rejection reason is required.",
      }));
      return;
    }

    setError(null);
    setNotice(null);
    setInflightAction({ licenseId: license.id, type: "reject" });

    try {
      const rejected = await rejectLicense(license.id, reason);
      setPendingLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      setProcessedLicenses((previous) => [
        toProcessedRow(license, rejected),
        ...previous.filter((item) => item.license_id !== license.id),
      ]);
      setOpenRejectId(null);
      setNotice(`License rejected for ${license.user_name}.`);
      void refreshProcessedLicenses();
    } catch (rejectError) {
      setError(getErrorMessage(rejectError, "Unable to reject license."));
    } finally {
      setInflightAction(null);
    }
  };

  const handleDownloadDocument = async (licenseId: number, userName: string) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId, type: "download" });

    try {
      const { blob, filename } = await downloadLicenseDocument(licenseId);
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(objectUrl);
      setNotice(`License document downloaded for ${userName}.`);
    } catch (downloadError) {
      setError(
        getErrorMessage(downloadError, "Unable to download license document."),
      );
    } finally {
      setInflightAction(null);
    }
  };

  const pendingColumns: TableColumn<LicenseWithUser>[] = [
    {
      key: "advisor",
      header: "Advisor",
      cell: (license) => (
        <div>
          <p className="font-semibold text-[#0a1633]">{license.user_name}</p>
          <p className="text-xs text-[#4c628a]">{license.user_email}</p>
        </div>
      ),
    },
    {
      key: "license",
      header: "License",
      cell: (license) => (
        <div>
          <p className="font-semibold text-[#0a1633]">
            {license.state} • {license.license_number}
          </p>
          <p className="text-xs text-[#4c628a]">
            {license.license_type?.trim() || "Type not provided"}
          </p>
        </div>
      ),
    },
    {
      key: "submitted",
      header: "Submitted",
      cell: (license) => (
        <span className="text-sm text-[#4c628a]">
          {formatDateTime(license.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "min-w-[280px]",
      cell: (license) => {
        const isOpen = openRejectId === license.id;
        const actionMatchesRow = inflightAction?.licenseId === license.id;
        const rejectError = rejectionErrors[license.id];

        return (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                className="px-3 py-1.5"
                loading={actionMatchesRow && inflightAction?.type === "download"}
                disabled={isBusy}
                onClick={() => {
                  void handleDownloadDocument(license.id, license.user_name);
                }}
              >
                Download Doc
              </Button>
              <Button
                variant="primary"
                className="px-3 py-1.5"
                loading={actionMatchesRow && inflightAction?.type === "approve"}
                disabled={isBusy}
                onClick={() => {
                  void handleApprove(license);
                }}
              >
                Approve
              </Button>
              <Button
                variant="danger"
                className="px-3 py-1.5"
                disabled={isBusy}
                onClick={() => handleRejectToggle(license.id)}
              >
                {isOpen ? "Cancel" : "Reject"}
              </Button>
            </div>

            {isOpen && (
              <div className="space-y-2 rounded-xl border border-[#ffd6d2] bg-[#fff8f7] p-3">
                <label
                  htmlFor={`rejection-reason-${license.id}`}
                  className="text-xs font-semibold uppercase tracking-wide text-[#8a1d1d]"
                >
                  Rejection reason
                </label>
                <textarea
                  id={`rejection-reason-${license.id}`}
                  className="w-full rounded-xl border border-[#e8d1cf] px-3 py-2 text-sm text-[#0a1633] focus:border-[#b42318] focus:outline-none"
                  rows={2}
                  value={rejectionReasons[license.id] ?? ""}
                  onChange={(event) =>
                    handleRejectReasonChange(license.id, event.target.value)
                  }
                  placeholder="Explain why this license is being rejected"
                />
                {rejectError && <p className="text-xs text-[#b42318]">{rejectError}</p>}

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="danger"
                    className="px-3 py-1.5"
                    loading={actionMatchesRow && inflightAction?.type === "reject"}
                    disabled={isBusy}
                    onClick={() => {
                      void handleRejectConfirm(license);
                    }}
                  >
                    Confirm Reject
                  </Button>
                  <Button
                    variant="secondary"
                    className="px-3 py-1.5"
                    disabled={isBusy}
                    onClick={() => handleRejectToggle(license.id)}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      },
    },
  ];

  const processedColumns: TableColumn<AdminLicenseDecisionRow>[] = [
    {
      key: "advisor",
      header: "Advisor",
      cell: (decision) => (
        <div>
          <p className="font-semibold text-[#0a1633]">{decision.user_name}</p>
          <p className="text-xs text-[#4c628a]">{decision.user_email}</p>
        </div>
      ),
    },
    {
      key: "license",
      header: "License",
      cell: (decision) => (
        <div>
          <p className="font-semibold text-[#0a1633]">
            {decision.state} • {decision.license_number}
          </p>
          <p className="text-xs text-[#4c628a]">
            {decision.license_type?.trim() || "Type not provided"}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      header: "Decision",
      cell: (decision) => (
        <span
          className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
            decision.decision_status === "verified"
              ? "bg-[#effdf1] text-[#1f6b2a]"
              : "bg-[#fff2f1] text-[#8a1d1d]"
          }`}
        >
          {decision.decision_status === "verified" ? "Approved" : "Rejected"}
        </span>
      ),
    },
    {
      key: "date",
      header: "Decision Date",
      cell: (decision) => (
        <span className="text-sm text-[#4c628a]">
          {formatDateTime(decision.decision_at)}
        </span>
      ),
    },
    {
      key: "reason",
      header: "Rejection Reason",
      cell: (decision) => (
        <span className="text-sm text-[#4c628a]">
          {decision.decision_status === "rejected"
            ? decision.rejection_reason || "Not provided"
            : "N/A"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      cell: (decision) => {
        const actionMatchesRow = inflightAction?.licenseId === decision.license_id;
        return (
          <Button
            variant="secondary"
            className="px-3 py-1.5"
            loading={actionMatchesRow && inflightAction?.type === "download"}
            disabled={isBusy}
            onClick={() => {
              void handleDownloadDocument(decision.license_id, decision.user_name);
            }}
          >
            Download Doc
          </Button>
        );
      },
    },
  ];

  return (
    <div className="space-y-6">
      {error && (
        <p
          className="rounded-xl border border-[#ffd6d2] bg-[#fff8f7] px-3 py-2 text-sm text-[#8a1d1d]"
          role="alert"
        >
          {error}
        </p>
      )}

      {notice && (
        <p
          className="rounded-xl border border-[#cdebcf] bg-[#effdf1] px-3 py-2 text-sm text-[#1f6b2a]"
          role="status"
        >
          {notice}
        </p>
      )}

      <Card
        title="Pending License Reviews"
        subtitle="Approve verified documents or reject with a required reason."
        action={
          <Button
            variant="secondary"
            className="px-3 py-1.5"
            disabled={loadingPending || loadingProcessed || isBusy}
            onClick={() => {
              void loadAdminTables();
            }}
          >
            Refresh
          </Button>
        }
      >
        <Table
          columns={pendingColumns}
          data={pendingLicenses}
          loading={loadingPending}
          rowKey={(license) => license.id}
          emptyMessage="No pending licenses to review."
        />
      </Card>

      <Card
        title="Processed License Decisions"
        subtitle="Current approved and rejected licenses with latest decision details."
      >
        <Table
          columns={processedColumns}
          data={processedLicenses}
          loading={loadingProcessed}
          rowKey={(decision) => decision.license_id}
          emptyMessage="No processed licenses to display."
        />
      </Card>
    </div>
  );
};

export default LicenseApproval;
