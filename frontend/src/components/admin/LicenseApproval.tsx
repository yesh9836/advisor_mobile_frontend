import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import {
  approveLicense,
  downloadLicenseDocument,
  getPendingLicenses,
  rejectLicense,
} from "@/api/admin";
import Button from "@/components/common/Button";
import Card from "@/components/common/Card";
import Table, { type TableColumn } from "@/components/common/Table";
import type { LicenseWithUser } from "@/types/license";

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

const formatDateTime = (value: string): string => {
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

const LicenseApproval = () => {
  const [licenses, setLicenses] = useState<LicenseWithUser[]>([]);
  const [loading, setLoading] = useState(true);
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

  const loadPendingLicenses = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const pending = await getPendingLicenses();
      setLicenses(pending);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Unable to load pending licenses."));
      setLicenses([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPendingLicenses();
  }, [loadPendingLicenses]);

  const isBusy = inflightAction !== null;

  const handleApprove = async (license: LicenseWithUser) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId: license.id, type: "approve" });

    try {
      await approveLicense(license.id);
      setLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      setNotice(`License approved for ${license.user_name}.`);
      if (openRejectId === license.id) {
        setOpenRejectId(null);
      }
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
      await rejectLicense(license.id, reason);
      setLicenses((previous) =>
        previous.filter((item) => item.id !== license.id),
      );
      setOpenRejectId(null);
      setNotice(`License rejected for ${license.user_name}.`);
    } catch (rejectError) {
      setError(getErrorMessage(rejectError, "Unable to reject license."));
    } finally {
      setInflightAction(null);
    }
  };

  const handleDownloadDocument = async (license: LicenseWithUser) => {
    setError(null);
    setNotice(null);
    setInflightAction({ licenseId: license.id, type: "download" });

    try {
      const { blob, filename } = await downloadLicenseDocument(license.id);
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(objectUrl);
      setNotice(`License document downloaded for ${license.user_name}.`);
    } catch (downloadError) {
      setError(
        getErrorMessage(downloadError, "Unable to download license document."),
      );
    } finally {
      setInflightAction(null);
    }
  };

  const columns: TableColumn<LicenseWithUser>[] = [
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
                  loading={
                    actionMatchesRow && inflightAction?.type === "download"
                  }
                  disabled={isBusy}
                  onClick={() => {
                    void handleDownloadDocument(license);
                  }}
                >
                  Download Doc
                </Button>
                <Button
                  variant="primary"
                  className="px-3 py-1.5"
                  loading={
                    actionMatchesRow && inflightAction?.type === "approve"
                  }
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
                  {rejectError && (
                    <p className="text-xs text-[#b42318]">{rejectError}</p>
                  )}

                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="danger"
                      className="px-3 py-1.5"
                      loading={
                        actionMatchesRow && inflightAction?.type === "reject"
                      }
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

  return (
    <Card
      title="Pending License Reviews"
      subtitle="Approve verified documents or reject with a required reason."
      action={
        <Button
          variant="secondary"
          className="px-3 py-1.5"
          disabled={loading || isBusy}
          onClick={() => {
            void loadPendingLicenses();
          }}
        >
          Refresh
        </Button>
      }
    >
      <div className="space-y-3">
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

        <Table
          columns={columns}
          data={licenses}
          loading={loading}
          rowKey={(license) => license.id}
          emptyMessage="No pending licenses to review."
        />
      </div>
    </Card>
  );
};

export default LicenseApproval;
