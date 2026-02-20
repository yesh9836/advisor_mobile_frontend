import { useEffect, useMemo, useRef, useState } from "react";

import { bulkImportLeadsAsAdmin } from "@/api/admin";
import { toImportSummary } from "@/components/admin/import-summary";
import type { LeadBulkImportResult } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportSuccess?: (result: LeadBulkImportResult) => void;
}

const ImportModal = ({ isOpen, onClose, onImportSuccess }: ImportModalProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<LeadBulkImportResult | null>(null);
  const [progressLabel, setProgressLabel] = useState("Waiting for file upload.");
  const progressTimerRef = useRef<number | null>(null);

  const stopProgressTimer = () => {
    if (progressTimerRef.current !== null) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (!isOpen) {
      stopProgressTimer();
      setFile(null);
      setImporting(false);
      setError(null);
      setProgress(0);
      setResult(null);
      setProgressLabel("Waiting for file upload.");
    }
  }, [isOpen]);

  useEffect(() => {
    return () => {
      stopProgressTimer();
    };
  }, []);

  const acceptedExtensions = useMemo(() => ".csv,text/csv", []);

  const handleRunImport = async () => {
    if (!file) {
      setError("Choose a CSV file before running import.");
      return;
    }

    setImporting(true);
    setError(null);
    setResult(null);
    setProgress(8);
    setProgressLabel("Uploading CSV...");
    stopProgressTimer();
    progressTimerRef.current = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 90) {
          return current;
        }
        return current + 7;
      });
      setProgressLabel("Processing rows...");
    }, 220);

    try {
      const response = await bulkImportLeadsAsAdmin(file);
      stopProgressTimer();
      setProgress(100);
      setProgressLabel("Import completed.");
      setResult(response);
      onImportSuccess?.(response);
    } catch (importError) {
      stopProgressTimer();
      setProgress(0);
      setProgressLabel("Import failed.");
      setResult(null);
      setError(getApiErrorMessage(importError, "Failed to import leads."));
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) {
    return null;
  }

  const summary = result ? toImportSummary(result) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="import-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.45)",
        display: "grid",
        placeItems: "center",
        zIndex: 110,
        padding: 16,
      }}
      onClick={() => {
        if (!importing) {
          onClose();
        }
      }}
    >
      <section
        className="panel stack"
        style={{
          width: "min(720px, 100%)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="page-header-row">
          <div>
            <h2 id="import-modal-title" style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>
              Run Lead Import
            </h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              CSV columns: state_code, mobile_phone, first_name, last_name, source
            </p>
          </div>

          <button type="button" className="btn btn-secondary" onClick={onClose} disabled={importing}>
            Close
          </button>
        </div>

        {error && <div className="alert">{error}</div>}

        <div
          style={{
            border: "2px dashed #cbd5e1",
            borderRadius: 16,
            padding: 24,
            textAlign: "center",
            background: "#f8fafc",
          }}
        >
          <p style={{ margin: 0, color: "#0f172a", fontSize: 22 }}>Upload CSV file</p>
          <p style={{ margin: "8px 0 0 0", color: "#64748b" }}>Choose a file to run bulk lead import.</p>

          <label className="btn btn-primary" style={{ marginTop: 16, display: "inline-block" }}>
            Choose File
            <input
              type="file"
              accept={acceptedExtensions}
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setError(null);
                setResult(null);
                setProgress(0);
                setProgressLabel("Ready to import.");
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

        {(importing || result || progress > 0) && (
          <section className="panel stack" style={{ background: "#f8fafc" }}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <strong style={{ color: "#0b1b49" }}>Import Progress</strong>
              <span style={{ color: "#475569", fontSize: 13 }}>{progress}%</span>
            </div>
            <div
              style={{
                width: "100%",
                height: 10,
                borderRadius: 999,
                background: "#e2e8f0",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${progress}%`,
                  height: "100%",
                  background: "#0b1b49",
                  transition: "width 0.2s ease",
                }}
              />
            </div>
            <p style={{ margin: 0, color: "#475569", fontSize: 13 }}>{progressLabel}</p>
          </section>
        )}

        {result && (
          <section className="panel stack" style={{ background: "#f8fafc" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: 24, color: "#0b1b49" }}>Import Results</h3>
              <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
                Summary for {file?.name ?? "uploaded file"}.
              </p>
            </div>

            <div className="grid-3">
              <div>
                <div style={{ color: "#64748b", fontSize: 13 }}>Inserted</div>
                <div style={{ color: "#0b1b49", fontWeight: 700, fontSize: 24 }}>
                  {result.success}
                </div>
              </div>
              <div>
                <div style={{ color: "#64748b", fontSize: 13 }}>Failed</div>
                <div style={{ color: "#0b1b49", fontWeight: 700, fontSize: 24 }}>
                  {result.failed}
                </div>
              </div>
              <div>
                <div style={{ color: "#64748b", fontSize: 13 }}>Duplicates</div>
                <div style={{ color: "#0b1b49", fontWeight: 700, fontSize: 24 }}>
                  {summary?.duplicateCount ?? 0}
                </div>
              </div>
            </div>

            {result.errors.length > 0 && (
              <div className="stack" style={{ gap: 6 }}>
                <strong style={{ color: "#0b1b49" }}>Top Errors</strong>
                {result.errors.slice(0, 5).map((entry, index) => (
                  <p key={`${entry.row}-${entry.error}-${index}`} style={{ margin: 0, color: "#9f1239", fontSize: 13 }}>
                    Row {entry.row}: {entry.error}
                  </p>
                ))}
                {result.errors.length > 5 && (
                  <p style={{ margin: 0, color: "#475569", fontSize: 12 }}>
                    +{result.errors.length - 5} more errors not shown
                  </p>
                )}
              </div>
            )}
          </section>
        )}

        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => void handleRunImport()}
            disabled={!file || importing}
          >
            {importing ? "Importing..." : result ? "Run Import Again" : "Run Import"}
          </button>
        </div>
      </section>
    </div>
  );
};

export default ImportModal;
