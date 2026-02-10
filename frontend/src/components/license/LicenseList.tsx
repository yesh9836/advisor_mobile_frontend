import axios from "axios";
import { useCallback, useEffect, useState } from "react";

import { getMyLicenses } from "@/api/licenses";
import Button from "@/components/common/Button";
import type { License } from "@/types/license";

interface LicenseListProps {
  refreshKey?: number;
}

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
}

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

  const loadLicenses = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getMyLicenses();
      setLicenses(data);
    } catch (error) {
      setError(getErrorMessage(error, "Unable to load licenses."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLicenses();
  }, [loadLicenses, refreshKey]);

  if (loading) {
    return (
      <section className="rounded-3xl border border-[#d9e4f8] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
        <h2 className="text-xl font-semibold text-[#0a1633]">My Licenses</h2>
        <p className="mt-3 text-sm text-[#4c628a]">Loading licenses...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="rounded-3xl border border-[#ffd6d2] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
        <h2 className="text-xl font-semibold text-[#0a1633]">My Licenses</h2>
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
    <section className="rounded-3xl border border-[#d9e4f8] bg-white p-5 shadow-[0_2px_10px_rgba(10,34,79,0.06)]">
      <h2 className="text-xl font-semibold text-[#0a1633]">My Licenses</h2>

      {licenses.length === 0 ? (
        <p className="mt-3 text-sm text-[#4c628a]">
          No licenses submitted yet.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {licenses.map((license) => (
            <article
              key={license.id}
              className="rounded-2xl border border-[#e7eefc] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-base font-semibold text-[#0a1633]">
                    {license.state} • {license.license_number}
                  </p>
                  <p className="text-sm text-[#4c628a]">
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

              <div className="mt-3 text-sm text-[#4c628a]">
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
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default LicenseList;
