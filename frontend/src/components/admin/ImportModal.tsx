import { useEffect, useMemo, useState } from "react";

import { bulkImportLeadsAsAdmin } from "@/api/admin";
import type { LeadBulkImportResult } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportSuccess?: (result: LeadBulkImportResult) => void;
}

const countDuplicates = (result: LeadBulkImportResult): number => {
  return result.errors.filter((entry) =>
    entry.error.toLowerCase().includes("duplicate"),
  ).length;
};

const ImportModal = ({ isOpen, onClose, onImportSuccess }: ImportModalProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      setFile(null);
      setImporting(false);
      setError(null);
    }
  }, [isOpen]);

  const acceptedExtensions = useMemo(() => ".csv,text/csv", []);

  const handleRunImport = async () => {
    if (!file) {
      setError("Choose a CSV file before running import.");
      return;
    }

    setImporting(true);
    setError(null);

    try {
      const response = await bulkImportLeadsAsAdmin(file);
      onImportSuccess?.(response);
      onClose();
    } catch (importError) {
      setError(getApiErrorMessage(importError, "Failed to import leads."));
    } finally {
      setImporting(false);
    }
  };

  if (!isOpen) {
    return null;
  }

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
      onClick={onClose}
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

        <div className="row" style={{ justifyContent: "flex-end" }}>
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
    </div>
  );
};

export interface ImportSummary {
  inserted: number;
  failed: number;
  duplicateCount: number;
}

export const toImportSummary = (
  result: LeadBulkImportResult,
): ImportSummary => {
  return {
    inserted: result.success,
    failed: result.failed,
    duplicateCount: countDuplicates(result),
  };
};

export default ImportModal;
