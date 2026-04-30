import { useCallback, useEffect, useMemo, useState } from "react";

import {
  approveLicense,
  downloadLicenseDocument,
  getPendingLicenses,
  getProcessedLicenses,
  previewLicenseDocument,
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
import { getApiErrorMessage } from "@/utils/api-error";

type ActionType = "approve" | "reject" | "download" | "preview";

interface PreviewState {
  isOpen: boolean;
  loading: boolean;
  licenseId: number | null;
  userName: string;
  objectUrl: string | null;
  contentType: string;
  error: string | null;
}

interface AdvisorOption {
  userId: number;
  label: string;
}

const PROCESSED_LICENSE_DECISION_LIMIT = 10;

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
    submission_type: "first_time",
    review_cycle: 1,
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
  const [selectedAdvisorId, setSelectedAdvisorId] = useState<string>("all");
  const [advisorQueryInput, setAdvisorQueryInput] = useState("");
  const [advisorQuery, setAdvisorQuery] = useState("");
  const [processedPage, setProcessedPage] = useState(1);
  const [preview, setPreview] = useState<PreviewState>({
    isOpen: false,
    loading: false,
    licenseId: null,
    userName: "",
    objectUrl: null,
    contentType: "",
    error: null,
  });

  const loadPendingLicenses = useCallback(async () => {
    setLoadingPending(true);
    try {
      const pending = await getPendingLicenses();
      setPendingLicenses(pending);
    } catch (pendingError) {
      setPendingLicenses([]);
      setError(
        getApiErrorMessage(pendingError, "Unable to load pending licenses."),
      );
    } finally {
      setLoadingPending(false);
    }
  }, []);

  const loadProcessedLicenses = useCallback(
    async (advisorId: string, queryText: string) => {
      setLoadingProcessed(true);
      try {
        const processed = await getProcessedLicenses({
          advisorId: advisorId === "all" ? undefined : Number(advisorId),
          advisorQuery: queryText.trim() || undefined,
        });
        setProcessedLicenses(processed);
      } catch (processedError) {
        setProcessedLicenses([]);
        setError(
          getApiErrorMessage(processedError, "Unable to load processed licenses."),
        );
      } finally {
        setLoadingProcessed(false);
      }
    },
    [],
  );

  const refreshAll = useCallback(async () => {
    setError(null);
    await Promise.all([
      loadPendingLicenses(),
      loadProcessedLicenses(selectedAdvisorId, advisorQuery),
    ]);
  }, [advisorQuery, loadPendingLicenses, loadProcessedLicenses, selectedAdvisorId]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    return () => {
      if (preview.objectUrl) {
        window.URL.revokeObjectURL(preview.objectUrl);
      }
    };
  }, [preview.objectUrl]);

  const advisorOptions = useMemo(() => {
    const byId = new Map<number, AdvisorOption>();

    pendingLicenses.forEach((license) => {
      byId.set(license.user_id, {
        userId: license.user_id,
        label: `${license.user_name} (${license.user_email})`,
      });
    });

    processedLicenses.forEach((row) => {
      if (!byId.has(row.user_id)) {
        byId.set(row.user_id, {
          userId: row.user_id,
          label: `${row.user_name} (${row.user_email})`,
        });
      }
    });

    return Array.from(byId.values()).sort((a, b) =>
      a.label.localeCompare(b.label),
    );
  }, [pendingLicenses, processedLicenses]);

  const isBusy = inflightAction !== null;
  const processedTotalPages = useMemo(
    () =>
      Math.max(
        1,
        Math.ceil(
          processedLicenses.length / PROCESSED_LICENSE_DECISION_LIMIT,
        ),
      ),
    [processedLicenses],
  );
  const visibleProcessedLicenses = useMemo(() => {
    const startIndex = (processedPage - 1) * PROCESSED_LICENSE_DECISION_LIMIT;
    const endIndex = startIndex + PROCESSED_LICENSE_DECISION_LIMIT;
    return processedLicenses.slice(startIndex, endIndex);
  }, [processedLicenses, processedPage]);

  const matchesProcessedFilters = useCallback(
    (row: AdminLicenseDecisionRow): boolean => {
      if (
        selectedAdvisorId !== "all" &&
        row.user_id !== Number(selectedAdvisorId)
      ) {
        return false;
      }
      if (!advisorQuery.trim()) {
        return true;
      }
      const term = advisorQuery.trim().toLowerCase();
      return (
        row.user_name.toLowerCase().includes(term) ||
        row.user_email.toLowerCase().includes(term)
      );
    },
    [advisorQuery, selectedAdvisorId],
  );

  const refreshProcessedLicenses = useCallback(async () => {
    await loadProcessedLicenses(selectedAdvisorId, advisorQuery);
  }, [advisorQuery, loadProcessedLicenses, selectedAdvisorId]);

  useEffect(() => {
    if (processedPage > processedTotalPages) {
      setProcessedPage(processedTotalPages);
    }
  }, [processedPage, processedTotalPages]);

  const handleApprove = async (license: LicenseWithUser) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId: license.id, type: "approve" });

    try {
      const approved = await approveLicense(license.id);
      const optimisticRow = toProcessedRow(license, approved);
      setPendingLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      if (matchesProcessedFilters(optimisticRow)) {
        setProcessedLicenses((previous) => [
          optimisticRow,
          ...previous.filter((item) => item.license_id !== license.id),
        ]);
      }
      setNotice(`License approved for ${license.user_name}.`);
      if (openRejectId === license.id) {
        setOpenRejectId(null);
      }
      void refreshProcessedLicenses();
    } catch (approveError) {
      setError(getApiErrorMessage(approveError, "Unable to approve license."));
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
      const optimisticRow = toProcessedRow(license, rejected);
      setPendingLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      if (matchesProcessedFilters(optimisticRow)) {
        setProcessedLicenses((previous) => [
          optimisticRow,
          ...previous.filter((item) => item.license_id !== license.id),
        ]);
      }
      setOpenRejectId(null);
      setNotice(`License rejected for ${license.user_name}.`);
      void refreshProcessedLicenses();
    } catch (rejectError) {
      setError(getApiErrorMessage(rejectError, "Unable to reject license."));
    } finally {
      setInflightAction(null);
    }
  };

  const handleClosePreview = () => {
    if (preview.objectUrl) {
      window.URL.revokeObjectURL(preview.objectUrl);
    }
    setPreview({
      isOpen: false,
      loading: false,
      licenseId: null,
      userName: "",
      objectUrl: null,
      contentType: "",
      error: null,
    });
  };

  const handlePreviewDocument = async (licenseId: number, userName: string) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId, type: "preview" });
    setPreview({
      isOpen: true,
      loading: true,
      licenseId,
      userName,
      objectUrl: null,
      contentType: "",
      error: null,
    });

    try {
      const { blob, contentType } = await previewLicenseDocument(licenseId);
      const objectUrl = window.URL.createObjectURL(blob);
      setPreview({
        isOpen: true,
        loading: false,
        licenseId,
        userName,
        objectUrl,
        contentType: contentType || blob.type || "",
        error: null,
      });
    } catch (previewError) {
      setPreview({
        isOpen: true,
        loading: false,
        licenseId,
        userName,
        objectUrl: null,
        contentType: "",
        error: getApiErrorMessage(
          previewError,
          "Unable to load document preview. You can still download the document.",
        ),
      });
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
        getApiErrorMessage(downloadError, "Unable to download license document."),
      );
    } finally {
      setInflightAction(null);
    }
  };

  const handleApplyFilters = async () => {
    setError(null);
    setProcessedPage(1);
    setAdvisorQuery(advisorQueryInput.trim());
    await loadProcessedLicenses(selectedAdvisorId, advisorQueryInput);
  };

  const handleAdvisorChange = async (value: string) => {
    setSelectedAdvisorId(value);
    setError(null);
    setProcessedPage(1);
    await loadProcessedLicenses(value, advisorQuery);
  };

  const handleClearFilters = async () => {
    setSelectedAdvisorId("all");
    setAdvisorQueryInput("");
    setAdvisorQuery("");
    setError(null);
    setProcessedPage(1);
    await loadProcessedLicenses("all", "");
  };

  const pendingColumns: TableColumn<LicenseWithUser>[] = [
    {
      key: "advisor",
      header: "Advisor",
      cell: (license) => (
        <div>
          <p className="font-semibold text-[#202860]">{license.user_name}</p>
          <p className="text-xs text-[#58707d]">{license.user_email}</p>
        </div>
      ),
    },
    {
      key: "license",
      header: "License",
      cell: (license) => (
        <div>
          <p className="font-semibold text-[#202860]">
            {license.state} • {license.license_number}
          </p>
          <p className="text-xs text-[#58707d]">
            {license.license_type?.trim() || "Type not provided"}
          </p>
        </div>
      ),
    },
    {
      key: "submitted",
      header: "Submitted",
      cell: (license) => (
        <span className="text-sm text-[#58707d]">
          {formatDateTime(license.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "min-w-[340px]",
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
                loading={actionMatchesRow && inflightAction?.type === "preview"}
                disabled={isBusy}
                onClick={() => {
                  void handlePreviewDocument(license.id, license.user_name);
                }}
              >
                View Doc
              </Button>
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
                  className="w-full rounded-xl border border-[#e8d1cf] px-3 py-2 text-sm text-[#202860] focus:border-[#b42318] focus:outline-none"
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
          <p className="font-semibold text-[#202860]">{decision.user_name}</p>
          <p className="text-xs text-[#58707d]">{decision.user_email}</p>
        </div>
      ),
    },
    {
      key: "license",
      header: "License",
      cell: (decision) => (
        <div>
          <p className="font-semibold text-[#202860]">
            {decision.state} • {decision.license_number}
          </p>
          <p className="text-xs text-[#58707d]">
            {decision.license_type?.trim() || "Type not provided"}
          </p>
        </div>
      ),
    },
    {
      key: "submission",
      header: "Submission Type",
      cell: (decision) => (
        <span className="text-sm text-[#58707d]">
          {decision.submission_type === "resubmission"
            ? "Resubmission"
            : "First-time"}
        </span>
      ),
    },
    {
      key: "cycle",
      header: "Review Cycle",
      cell: (decision) => (
        <span className="text-sm text-[#58707d]">{decision.review_cycle}</span>
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
        <span className="text-sm text-[#58707d]">
          {formatDateTime(decision.decision_at)}
        </span>
      ),
    },
    {
      key: "reason",
      header: "Rejection Reason",
      cell: (decision) => (
        <span className="text-sm text-[#58707d]">
          {decision.decision_status === "rejected"
            ? decision.rejection_reason || "Not provided"
            : "N/A"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Actions",
      className: "min-w-[190px]",
      cell: (decision) => {
        const actionMatchesRow = inflightAction?.licenseId === decision.license_id;
        return (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              className="px-3 py-1.5"
              loading={actionMatchesRow && inflightAction?.type === "preview"}
              disabled={isBusy}
              onClick={() => {
                void handlePreviewDocument(decision.license_id, decision.user_name);
              }}
            >
              View Doc
            </Button>
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
          </div>
        );
      },
    },
  ];

  const isImagePreview = preview.contentType.startsWith("image/");
  const isPdfPreview = preview.contentType.includes("application/pdf");

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
              void refreshAll();
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
        <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto_auto]">
          <label className="flex flex-col gap-1 text-sm text-[#58707d]">
            <span>Advisor</span>
            <select
              value={selectedAdvisorId}
              aria-label="Filter by advisor"
              className="rounded-xl border border-[#d8e8ee] px-3 py-2 text-sm text-[#202860] focus:border-[#18a0b8] focus:outline-none"
              onChange={(event) => {
                void handleAdvisorChange(event.target.value);
              }}
            >
              <option value="all">All advisors</option>
              {advisorOptions.map((option) => (
                <option key={option.userId} value={option.userId}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-[#58707d]">
            <span>Search name or email</span>
            <input
              value={advisorQueryInput}
              aria-label="Search advisor"
              className="rounded-xl border border-[#d8e8ee] px-3 py-2 text-sm text-[#202860] focus:border-[#18a0b8] focus:outline-none"
              onChange={(event) => setAdvisorQueryInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void handleApplyFilters();
                }
              }}
              placeholder="Type advisor name or email"
            />
          </label>
          <div className="flex items-end">
            <Button
              variant="secondary"
              className="w-full px-3 py-2"
              disabled={loadingProcessed || isBusy}
              onClick={() => {
                void handleApplyFilters();
              }}
            >
              Apply Filters
            </Button>
          </div>
          <div className="flex items-end">
            <Button
              variant="secondary"
              className="w-full px-3 py-2"
              disabled={loadingProcessed || isBusy}
              onClick={() => {
                void handleClearFilters();
              }}
            >
              Clear
            </Button>
          </div>
        </div>

        <Table
          columns={processedColumns}
          data={visibleProcessedLicenses}
          loading={loadingProcessed}
          rowKey={(decision) => decision.license_id}
          emptyMessage="No processed licenses to display."
        />

        <div
          className="row"
          style={{ justifyContent: "space-between", alignItems: "center", marginTop: 8 }}
        >
          <span style={{ color: "#58707d", fontSize: 14 }}>
            Page {processedPage} of {processedTotalPages} •{" "}
            {processedLicenses.length} total processed licenses
          </span>
          <div className="row">
            <Button
              variant="secondary"
              className="px-3 py-1.5"
              disabled={loadingProcessed || isBusy || processedPage <= 1}
              onClick={() =>
                setProcessedPage((current) => Math.max(1, current - 1))
              }
            >
              Previous
            </Button>
            <Button
              variant="secondary"
              className="px-3 py-1.5"
              disabled={
                loadingProcessed ||
                isBusy ||
                processedPage >= processedTotalPages
              }
              onClick={() =>
                setProcessedPage((current) =>
                  Math.min(processedTotalPages, current + 1),
                )
              }
            >
              Next
            </Button>
          </div>
        </div>
      </Card>

      {preview.isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#202860]/55 px-4"
          role="dialog"
          aria-modal="true"
          aria-label="License document preview"
        >
          <div className="w-full max-w-4xl rounded-2xl bg-white p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[#202860]">
                  License Preview
                </h3>
                <p className="text-sm text-[#58707d]">{preview.userName}</p>
              </div>
              <Button
                variant="secondary"
                className="px-3 py-1.5"
                onClick={handleClosePreview}
              >
                Close
              </Button>
            </div>

            <div className="h-[65vh] overflow-auto rounded-xl border border-[#d8e8ee] bg-[#f4fbfc] p-3">
              {preview.loading && (
                <p className="text-sm text-[#58707d]">Loading preview...</p>
              )}

              {!preview.loading && preview.error && (
                <div className="space-y-3">
                  <p className="text-sm text-[#8a1d1d]">{preview.error}</p>
                  {preview.licenseId !== null && (
                    <Button
                      variant="secondary"
                      className="px-3 py-1.5"
                      onClick={() => {
                        const targetLicenseId = preview.licenseId;
                        if (targetLicenseId !== null) {
                          void handleDownloadDocument(targetLicenseId, preview.userName);
                        }
                      }}
                    >
                      Download Doc
                    </Button>
                  )}
                </div>
              )}

              {!preview.loading &&
                !preview.error &&
                preview.objectUrl &&
                isImagePreview && (
                  <img
                    src={preview.objectUrl}
                    alt="License document preview"
                    className="mx-auto max-h-[60vh] rounded-lg"
                  />
                )}

              {!preview.loading &&
                !preview.error &&
                preview.objectUrl &&
                isPdfPreview && (
                  <iframe
                    src={preview.objectUrl}
                    title="License PDF preview"
                    className="h-[60vh] w-full rounded-lg border border-[#d8e8ee]"
                  />
                )}

              {!preview.loading &&
                !preview.error &&
                preview.objectUrl &&
                !isImagePreview &&
                !isPdfPreview && (
                  <div className="space-y-3">
                    <p className="text-sm text-[#58707d]">
                      Inline preview is not available for this file type.
                    </p>
                    {preview.licenseId !== null && (
                      <Button
                        variant="secondary"
                        className="px-3 py-1.5"
                        onClick={() => {
                          const targetLicenseId = preview.licenseId;
                          if (targetLicenseId !== null) {
                            void handleDownloadDocument(targetLicenseId, preview.userName);
                          }
                        }}
                      >
                        Download Doc
                      </Button>
                    )}
                  </div>
                )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LicenseApproval;
