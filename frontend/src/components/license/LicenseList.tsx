import { useCallback, useEffect, useState } from "react";

import { getMyLicenses, resubmitLicense } from "@/api/licenses";
import Button from "@/components/common/Button";
import {
  LICENSE_DOCUMENT_ACCEPT,
  validateLicenseDocument,
} from "@/components/license/documentUpload";
import type { License } from "@/types/license";
import { getApiErrorMessage } from "@/utils/api-error";
import { isRequestCanceled, useLatestRequest } from "@/utils/request-control";

interface LicenseListProps {
  refreshKey?: number;
}

const formatDate = (value: string | null): string => {
  if (!value) {
    return "-";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const getStatusBadgeClass = (
  status: License["verification_status"],
): string => {
  if (status === "verified") {
    return "border-[#a7f3d0] bg-[#ecfdf3] text-[#047857]";
  }

  if (status === "rejected") {
    return "border-[#fecaca] bg-[#fff1f2] text-[#b42318]";
  }

  return "border-[#cde1ff] bg-[#eff6ff] text-[#1d4ed8]";
};

const LicenseList = ({ refreshKey = 0 }: LicenseListProps) => {
  const [licenses, setLicenses] = useState<License[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [openResubmitId, setOpenResubmitId] = useState<number | null>(null);
  const [resubmitFiles, setResubmitFiles] = useState<Record<number, File>>({});
  const [resubmitErrors, setResubmitErrors] = useState<Record<number, string>>({});
  const [resubmittingLicenseId, setResubmittingLicenseId] = useState<number | null>(
    null,
  );
  const { beginRequest, isLatestRequest } = useLatestRequest();

  const loadLicenses = useCallback(async () => {
    const { requestId, signal } = beginRequest();
    setLoading(true);
    setError(null);
    setNotice(null);

    try {
      const data = await getMyLicenses({ signal });
      if (!isLatestRequest(requestId)) {
        return;
      }
      setLicenses(data);
    } catch (error) {
      if (!isLatestRequest(requestId) || isRequestCanceled(error)) {
        return;
      }
      setError(getApiErrorMessage(error, "Unable to load licenses."));
    } finally {
      if (isLatestRequest(requestId)) {
        setLoading(false);
      }
    }
  }, [beginRequest, isLatestRequest]);

  useEffect(() => {
    void loadLicenses();
  }, [loadLicenses, refreshKey]);

  const handleResubmitToggle = (licenseId: number) => {
    setOpenResubmitId((previous) => (previous === licenseId ? null : licenseId));
    setResubmitErrors((previous) => {
      const next = { ...previous };
      delete next[licenseId];
      return next;
    });
  };

  const handleFileSelection = (licenseId: number, file: File | null) => {
    if (!file) {
      setResubmitFiles((previous) => {
        const next = { ...previous };
        delete next[licenseId];
        return next;
      });
      return;
    }

    setResubmitFiles((previous) => ({
      ...previous,
      [licenseId]: file,
    }));
    setResubmitErrors((previous) => {
      const next = { ...previous };
      delete next[licenseId];
      return next;
    });
  };

  const handleResubmit = async (license: License) => {
    const file = resubmitFiles[license.id];
    if (!file) {
      setResubmitErrors((previous) => ({
        ...previous,
        [license.id]: "Please upload a replacement document.",
      }));
      return;
    }

    const fileError = validateLicenseDocument(file);
    if (fileError) {
      setResubmitErrors((previous) => ({
        ...previous,
        [license.id]: fileError,
      }));
      return;
    }

    const formData = new FormData();
    formData.append("document", file);

    setError(null);
    setNotice(null);
    setResubmittingLicenseId(license.id);

    try {
      const updated = await resubmitLicense(license.id, formData);
      setLicenses((previous) =>
        previous.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(
        `License ${license.state} • ${license.license_number} resubmitted successfully.`,
      );
      setOpenResubmitId(null);
      setResubmitFiles((previous) => {
        const next = { ...previous };
        delete next[license.id];
        return next;
      });
      setResubmitErrors((previous) => {
        const next = { ...previous };
        delete next[license.id];
        return next;
      });
    } catch (resubmitError) {
      setResubmitErrors((previous) => ({
        ...previous,
        [license.id]: getApiErrorMessage(
          resubmitError,
          "Unable to resubmit license.",
        ),
      }));
    } finally {
      setResubmittingLicenseId(null);
    }
  };

  if (loading) {
    return (
      <section className="rounded-3xl border border-[#d8e8ee] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
        <h2 className="text-xl font-semibold text-[#202860]">My Licenses</h2>
        <p className="mt-3 text-sm text-[#58707d]">Loading licenses...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-3xl border border-[#ffd6d2] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
        <h2 className="text-xl font-semibold text-[#202860]">My Licenses</h2>
        <p className="mt-3 text-sm text-[#8a1d1d]">{error}</p>
        <div className="mt-4">
          <Button variant="secondary" onClick={() => void loadLicenses()}>
            Retry
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-3xl border border-[#d8e8ee] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
      <h2 className="text-xl font-semibold text-[#202860]">My Licenses</h2>
      {notice && (
        <div className="mt-3 rounded-xl border border-[#b7ebc6] bg-[#ebfff1] px-3 py-2 text-sm text-[#0f5132]">
          {notice}
        </div>
      )}

      {licenses.length === 0 ? (
        <p className="mt-3 text-sm text-[#58707d]">
          No licenses submitted yet.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {licenses.map((license) => (
            <article
              key={license.id}
              className="rounded-2xl border border-[#d8e8ee] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-[#202860]">
                    {license.state} • {license.license_number}
                  </p>
                  <p className="text-sm text-[#58707d]">
                    Type: {license.license_type?.trim() || "Not provided"}
                  </p>
                </div>

                <span
                  className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${getStatusBadgeClass(
                    license.verification_status,
                  )}`}
                >
                  {license.verification_status}
                </span>
              </div>

              <div className="mt-3 text-sm text-[#58707d]">
                <p>Submitted: {formatDate(license.created_at)}</p>
                {license.verification_status === "verified" && (
                  <p>Verified: {formatDate(license.verified_at)}</p>
                )}
                {license.verification_status === "rejected" &&
                  license.rejection_reason && (
                    <p className="text-[#8a1d1d]">
                      Rejection reason: {license.rejection_reason}
                    </p>
                  )}
              </div>

              {license.verification_status === "rejected" && (
                <div className="mt-4 space-y-3">
                  <Button
                    variant="secondary"
                    onClick={() => handleResubmitToggle(license.id)}
                  >
                    {openResubmitId === license.id
                      ? "Cancel Resubmit"
                      : "Resubmit"}
                  </Button>

                  {openResubmitId === license.id && (
                    <div className="space-y-2 rounded-xl border border-[#d8e8ee] bg-[#f4fbfc] p-3">
                      <label
                        htmlFor={`resubmit-document-${license.id}`}
                        className="block text-xs font-semibold uppercase tracking-wide text-[#58707d]"
                      >
                        Upload replacement document (PDF, JPG, JPEG, or PNG)
                      </label>
                      <input
                        id={`resubmit-document-${license.id}`}
                        type="file"
                        accept={LICENSE_DOCUMENT_ACCEPT}
                        onChange={(event) =>
                          handleFileSelection(
                            license.id,
                            event.target.files?.[0] ?? null,
                          )
                        }
                        className="w-full rounded-xl border border-[#d8e8ee] px-3 py-2 text-sm text-[#202860] file:mr-3 file:rounded-full file:border-0 file:bg-[#e8fbff] file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-[#202860]"
                      />

                      {resubmitErrors[license.id] && (
                        <p className="text-xs text-[#b42318]">
                          {resubmitErrors[license.id]}
                        </p>
                      )}

                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="primary"
                          loading={resubmittingLicenseId === license.id}
                          disabled={resubmittingLicenseId === license.id}
                          onClick={() => {
                            void handleResubmit(license);
                          }}
                        >
                          {resubmittingLicenseId === license.id
                            ? "Resubmitting..."
                            : "Confirm Resubmit"}
                        </Button>
                        <Button
                          variant="secondary"
                          disabled={resubmittingLicenseId === license.id}
                          onClick={() => handleResubmitToggle(license.id)}
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default LicenseList;
