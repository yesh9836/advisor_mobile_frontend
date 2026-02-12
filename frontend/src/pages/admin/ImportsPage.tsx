import { useEffect, useMemo, useState } from "react";

import { bulkImportLeadsAsAdmin, getAuditLogs } from "@/api/admin";
import type { AuditLog, LeadBulkImportResult } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

interface ImportHistoryItem {
  id: number;
  created_at: string;
  scanned: number;
  inserted: number;
  skipped_duplicates: number;
  failed: number;
}

const countDuplicates = (result: LeadBulkImportResult | null): number => {
  if (!result) return 0;

  return result.errors.filter((entry) =>
    entry.error.toLowerCase().includes("duplicate"),
  ).length;
};

const toNumber = (value: unknown): number => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  return 0;
};

const toRecord = (value: unknown): Record<string, unknown> => {
  if (typeof value === "object" && value !== null) {
    return value as Record<string, unknown>;
  }
  return {};
};

const mapAuditLogToImportHistory = (item: AuditLog): ImportHistoryItem => {
  const meta = toRecord(item.meta_data);

  const scanned = toNumber(meta.scanned);
  const insertedFromMeta = toNumber(meta.inserted);
  const successFallback = toNumber(meta.success);
  const inserted = insertedFromMeta || successFallback;
  const failed = toNumber(meta.failed);
  const skippedDuplicates = toNumber(meta.skipped_duplicates);

  return {
    id: item.id,
    created_at: item.created_at,
    scanned,
    inserted,
    skipped_duplicates: skippedDuplicates,
    failed,
  };
};

const formatImportDate = (isoTimestamp: string): string => {
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

const ImportsPage = () => {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<LeadBulkImportResult | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const scannedRows = useMemo(() => {
    if (!result) return 0;
    return result.success + result.failed;
  }, [result]);

  const loadImportHistory = async () => {
    setHistoryLoading(true);

    try {
      const response = await getAuditLogs(
        {
          action: "lead_bulk_import",
          entity_type: "LeadImport",
        },
        1,
        10,
      );
      setHistory(response.items.map(mapAuditLogToImportHistory));
    } catch (loadError) {
      setHistory([]);
      setError(getApiErrorMessage(loadError, "Failed to load import history."));
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    void loadImportHistory();
  }, []);

  const handleRunImport = async () => {
    if (!file) {
      setError("Choose a CSV file before running import.");
      return;
    }

    setImporting(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await bulkImportLeadsAsAdmin(file);
      setResult(response);
      setSuccess(`Import completed. Inserted ${response.success} leads.`);
      await loadImportHistory();
    } catch (importError) {
      setResult(null);
      setError(getApiErrorMessage(importError, "Failed to import leads."));
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="page">
      <div>
        <h1>Admin • Imports</h1>
        <p className="page-subtitle">Upload CSV / JSON to add new leads.</p>
      </div>

      {error && <div className="alert">{error}</div>}
      {success && <div className="success">{success}</div>}

      <section className="grid-main">
        <article className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Upload File</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              CSV columns: state_code, mobile_phone, first_name, last_name, source
            </p>
          </div>

          <div
            style={{
              border: "2px dashed #cbd5e1",
              borderRadius: 16,
              padding: 28,
              textAlign: "center",
              background: "#f8fafc",
            }}
          >
            <p style={{ margin: 0, color: "#0f172a", fontSize: 24 }}>Drag & drop CSV here</p>
            <p style={{ margin: "8px 0 0 0", color: "#64748b" }}>or click to browse</p>

            <label className="btn btn-primary" style={{ marginTop: 16, display: "inline-block" }}>
              Choose File
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(event) => {
                  setFile(event.target.files?.[0] ?? null);
                  setResult(null);
                  setError(null);
                  setSuccess(null);
                }}
                style={{ display: "none" }}
              />
            </label>

            {file && (
              <div style={{ marginTop: 12, color: "#334155" }}>
                Selected: <strong>{file.name}</strong>
              </div>
            )}
          </div>

          <section className="panel" style={{ background: "#f1f5f9" }}>
            <h3 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Import Preview</h3>

            <div className="grid-3" style={{ marginTop: 12 }}>
              <div>
                <div className="metric-title">Rows</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#0b1b49" }}>
                  {scannedRows.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="metric-title">Valid</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#0b1b49" }}>
                  {(result?.success ?? 0).toLocaleString()}
                </div>
              </div>
              <div>
                <div className="metric-title">Duplicates</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: "#0b1b49" }}>
                  {countDuplicates(result).toLocaleString()}
                </div>
              </div>
            </div>

            <div className="row" style={{ marginTop: 14 }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleRunImport()}
                disabled={!file || importing}
              >
                {importing ? "Importing..." : "Run Import"}
              </button>
            </div>
          </section>
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Import History</h2>
          </div>

          {historyLoading && <div style={{ color: "#475569" }}>Loading import history...</div>}

          {!historyLoading && history.length === 0 && (
            <div style={{ color: "#475569" }}>No import runs yet.</div>
          )}

          {!historyLoading && history.map((entry) => (
            <section key={entry.id} className="panel" style={{ background: "#f8fafc" }}>
              <h3 style={{ margin: 0, fontSize: 26, color: "#0b1b49" }}>
                {formatImportDate(entry.created_at)}
              </h3>
              <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
                {entry.scanned.toLocaleString()} rows • {entry.inserted.toLocaleString()} inserted
              </p>
              <p style={{ margin: "6px 0 0 0", color: "#64748b", fontSize: 14 }}>
                {entry.skipped_duplicates.toLocaleString()} duplicates • {entry.failed.toLocaleString()} failed
              </p>
            </section>
          ))}
        </aside>
      </section>
    </div>
  );
};

export default ImportsPage;
