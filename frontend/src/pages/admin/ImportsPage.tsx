import { useCallback, useEffect, useMemo, useState } from "react";

import { getAuditLogs } from "@/api/admin";
import ImportModal from "@/components/admin/ImportModal";
import { toImportSummary } from "@/components/admin/import-summary";
import type { AuditLog } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

interface ImportHistoryItem {
  id: number;
  created_at: string;
  scanned: number;
  inserted: number;
  skipped_duplicates: number;
  failed: number;
}

const HISTORY_PAGE_SIZE = 10;

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
  const [history, setHistory] = useState<ImportHistoryItem[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [runSuccess, setRunSuccess] = useState<string | null>(null);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(historyTotal / HISTORY_PAGE_SIZE)),
    [historyTotal],
  );

  const loadImportHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);

    try {
      const response = await getAuditLogs(
        {
          action: "lead_bulk_import",
          entity_type: "LeadImport",
        },
        historyPage,
        HISTORY_PAGE_SIZE,
      );

      setHistory(response.items.map(mapAuditLogToImportHistory));
      setHistoryTotal(response.total);
    } catch (loadError) {
      setHistory([]);
      setHistoryTotal(0);
      setHistoryError(getApiErrorMessage(loadError, "Failed to load import history."));
    } finally {
      setHistoryLoading(false);
    }
  }, [historyPage]);

  useEffect(() => {
    void loadImportHistory();
  }, [loadImportHistory]);

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • Imports</h1>
          <p className="page-subtitle">Dedicated history of bulk lead import runs.</p>
        </div>

        <div className="row" style={{ flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void loadImportHistory()}
            disabled={historyLoading}
          >
            Refresh History
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setModalOpen(true)}
          >
            Run Import
          </button>
        </div>
      </div>

      {historyError && <div className="alert">{historyError}</div>}
      {runSuccess && <div className="success">{runSuccess}</div>}

      <section className="panel stack">
        <div>
          <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Import Run History</h2>
          <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
            Audit trail of scanned rows, inserts, duplicates, and failures.
          </p>
        </div>

        {historyLoading && <div style={{ color: "#475569" }}>Loading import history...</div>}

        {!historyLoading && history.length === 0 && (
          <div style={{ color: "#475569" }}>No import runs yet.</div>
        )}

        {!historyLoading && history.map((entry) => (
          <section
            key={entry.id}
            className="panel"
            style={{
              background: "#f8fafc",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div>
              <h3 style={{ margin: 0, fontSize: 24, color: "#0b1b49" }}>
                {formatImportDate(entry.created_at)}
              </h3>
              <p style={{ margin: "8px 0 0 0", color: "#475569" }}>
                {entry.scanned.toLocaleString()} rows scanned
              </p>
            </div>

            <div style={{ textAlign: "right" }}>
              <div style={{ color: "#0b1b49", fontWeight: 700 }}>
                {entry.inserted.toLocaleString()} inserted
              </div>
              <div style={{ marginTop: 6, color: "#64748b", fontSize: 14 }}>
                {entry.skipped_duplicates.toLocaleString()} duplicates • {entry.failed.toLocaleString()} failed
              </div>
            </div>
          </section>
        ))}

        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: "#475569", fontSize: 14 }}>
            Page {historyPage} of {totalPages} • {historyTotal} total runs
          </span>
          <div className="row">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={historyPage <= 1 || historyLoading}
              onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={historyPage >= totalPages || historyLoading}
              onClick={() => setHistoryPage((prev) => prev + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>

      <ImportModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onImportSuccess={(result) => {
          const summary = toImportSummary(result);
          setRunSuccess(
            `Import completed. Inserted ${summary.inserted} leads, ${summary.duplicateCount} duplicates, ${summary.failed} failed rows.`,
          );
          setHistoryPage(1);
          if (historyPage === 1) {
            void loadImportHistory();
          }
        }}
      />
    </div>
  );
};

export default ImportsPage;
