import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { downloadLeads, getLeads, saveLeadOutcome } from "@/api/leads";
import {
  formatDateTime,
  stageClassName,
  toDisplayName,
  toDisplayStage,
  toInitials,
  type LeadStage,
} from "@/pages/advisor/leadPresentation";
import type { Lead, LeadFilters, LeadOutcomeStatus } from "@/types/lead";
import { getApiErrorMessage } from "@/utils/api-error";
import { isRequestCanceled, useLatestRequest } from "@/utils/request-control";

type StageFilter = "All" | LeadStage;
type DeliveryFilter = "All" | "Available" | "Delivered";

interface InboxLead {
  id: number;
  initials: string;
  name: string;
  state: string;
  isDownloaded: boolean;
  piiUnlocked: boolean;
  stage: LeadStage;
  headline: string;
  assets: string;
  phone: string;
  dateTime: string;
}

const STAGES: LeadStage[] = ["New", "Contacted", "Appointment Set"];

const STAGE_TO_STATUS: Record<LeadStage, LeadOutcomeStatus> = {
  New: "new",
  Contacted: "contacted",
  "Appointment Set": "appointment_set",
};

const PAGE_SIZE = 25;
const SEARCH_DEBOUNCE_MS = 300;

const DELIVERY_FILTER_TO_QUERY: Record<
  DeliveryFilter,
  NonNullable<LeadFilters["delivery_status"]>
> = {
  All: "all",
  Available: "available",
  Delivered: "delivered",
};

const STAGE_FILTER_TO_QUERY: Record<
  StageFilter,
  NonNullable<LeadFilters["outcome_status"]>
> = {
  All: "all",
  New: "new",
  Contacted: "contacted",
  "Appointment Set": "appointment_set",
};

const toInboxLead = (lead: Lead): InboxLead => {
  const piiUnlocked = Boolean(lead.pii_unlocked ?? lead.is_downloaded);
  return {
    id: lead.id,
    initials: piiUnlocked ? toInitials(lead.first_name, lead.last_name) : "LK",
    name: piiUnlocked ? toDisplayName(lead) : "Locked Lead",
    state: (lead.state_code || "NA").toUpperCase(),
    isDownloaded: Boolean(lead.is_downloaded),
    piiUnlocked,
    stage: toDisplayStage(lead.outcome_status),
    headline: piiUnlocked
      ? lead.most_important_retirement_activity || "No details available"
      : "Details unlock after delivery",
    assets: piiUnlocked
      ? lead.total_investable_assets_range || "0"
      : "Locked",
    phone: piiUnlocked ? lead.mobile_phone || "Not available" : "Unlock after delivery",
    dateTime: formatDateTime(lead.received_at ?? lead.created_at),
  };
};

const LeadsPage = () => {
  const navigate = useNavigate();

  const [leads, setLeads] = useState<InboxLead[]>([]);
  const [selectedLeadId, setSelectedLeadId] = useState<number | null>(null);
  const [statusByLeadId, setStatusByLeadId] = useState<
    Record<number, LeadStage>
  >({});
  const [notesByLeadId, setNotesByLeadId] = useState<Record<number, string>>(
    {},
  );

  const [stageFilter, setStageFilter] = useState<StageFilter>("All");
  const [deliveryFilter, setDeliveryFilter] = useState<DeliveryFilter>("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalLeads, setTotalLeads] = useState(0);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);
  const { beginRequest, isLatestRequest } = useLatestRequest();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [searchQuery]);

  const loadInbox = useCallback(async () => {
    const { requestId, signal } = beginRequest();
    setLoading(true);
    setError(null);

    try {
      const response = await getLeads(
        currentPage,
        PAGE_SIZE,
        {
          delivery_status: DELIVERY_FILTER_TO_QUERY[deliveryFilter],
          outcome_status: STAGE_FILTER_TO_QUERY[stageFilter],
          ...(debouncedSearchQuery ? { search: debouncedSearchQuery } : {}),
        },
        { signal },
      );
      if (!isLatestRequest(requestId)) {
        return;
      }

      setTotalLeads(response.total);
      const lastPage = Math.max(1, Math.ceil(response.total / PAGE_SIZE));
      if (response.total > 0 && currentPage > lastPage) {
        setCurrentPage(lastPage);
        return;
      }

      const mapped = response.items.map((lead) => toInboxLead(lead));
      const nextStatusByLeadId: Record<number, LeadStage> = {};
      const nextNotesByLeadId: Record<number, string> = {};

      for (const lead of response.items) {
        nextStatusByLeadId[lead.id] = toDisplayStage(lead.outcome_status);
        nextNotesByLeadId[lead.id] = lead.outcome_notes ?? "";
      }

      setLeads(mapped);
      setStatusByLeadId(nextStatusByLeadId);
      setNotesByLeadId(nextNotesByLeadId);

      setSelectedLeadId((previousLeadId) => {
        if (mapped.length === 0) {
          return null;
        }
        return mapped.some((lead) => lead.id === previousLeadId)
          ? previousLeadId
          : mapped[0].id;
      });
    } catch (loadError) {
      if (!isLatestRequest(requestId) || isRequestCanceled(loadError)) {
        return;
      }
      setLeads([]);
      setTotalLeads(0);
      setSelectedLeadId(null);
      setError(getApiErrorMessage(loadError, "Unable to load lead inbox."));
    } finally {
      if (isLatestRequest(requestId)) {
        setLoading(false);
      }
    }
  }, [
    beginRequest,
    currentPage,
    debouncedSearchQuery,
    deliveryFilter,
    isLatestRequest,
    stageFilter,
  ]);

  useEffect(() => {
    void loadInbox();
  }, [loadInbox, reloadTick]);

  const selectedLead = useMemo(() => {
    if (selectedLeadId === null) {
      return null;
    }
    return leads.find((lead) => lead.id === selectedLeadId) ?? null;
  }, [leads, selectedLeadId]);

  const totalPages = Math.max(1, Math.ceil(totalLeads / PAGE_SIZE));

  const selectedStatus = selectedLead
    ? (statusByLeadId[selectedLead.id] ?? selectedLead.stage)
    : "New";
  const selectedNotes = selectedLead
    ? (notesByLeadId[selectedLead.id] ?? "")
    : "";

  const handleExportCsv = async () => {
    setDownloading(true);
    setError(null);

    try {
      const blob = await downloadLeads();
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `leads_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      window.URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(getApiErrorMessage(downloadError, "Unable to export CSV."));
    } finally {
      setDownloading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedLead) return;

    setSaving(true);
    setError(null);
    setSaveMessage(null);

    try {
      const payload = {
        status: STAGE_TO_STATUS[selectedStatus],
        notes: selectedNotes.trim() || null,
      };

      const outcome = await saveLeadOutcome(selectedLead.id, payload);
      const savedStage = toDisplayStage(outcome.status);

      setStatusByLeadId((previous) => ({
        ...previous,
        [selectedLead.id]: savedStage,
      }));
      setNotesByLeadId((previous) => ({
        ...previous,
        [selectedLead.id]: outcome.notes ?? "",
      }));

      setSaveMessage(`Lead updates saved for ${selectedLead.name}.`);
      window.setTimeout(() => setSaveMessage(null), 2200);
      setReloadTick((previous) => previous + 1);
    } catch (saveError) {
      setError(getApiErrorMessage(saveError, "Unable to save lead outcome."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Lead Inbox</h1>
          <p className="page-subtitle">
            Leads are delivered here instantly after purchase. Track outcomes
            and export anytime.
          </p>
        </div>
        <div className="row">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleExportCsv}
            disabled={downloading}
          >
            {downloading ? "Exporting..." : "Export CSV"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate("/subscription")}
          >
            Buy Leads
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
      {saveMessage && <div className="success">{saveMessage}</div>}

      <section className="inbox-grid">
        <article className="panel">
          <div className="list-header">
            <div className="list-title">Leads ({totalLeads})</div>
            <div className="row">
              <input
                value={searchQuery}
                onChange={(event) => {
                  setSearchQuery(event.target.value);
                  setCurrentPage(1);
                }}
                className="btn btn-secondary"
                style={{ borderRadius: 10, padding: "8px 12px", width: 200 }}
                aria-label="Lead search"
                placeholder="Search name, phone..."
              />
              <select
                value={stageFilter}
                onChange={(event) => {
                  setStageFilter(event.target.value as StageFilter);
                  setCurrentPage(1);
                }}
                className="btn btn-secondary"
                style={{ borderRadius: 10, padding: "8px 12px" }}
                aria-label="Lead filter"
              >
                <option value="All">All</option>
                <option value="Contacted">Contacted</option>
                <option value="Appointment Set">Appointment Set</option>
              </select>
              <select
                value={deliveryFilter}
                onChange={(event) => {
                  setDeliveryFilter(event.target.value as DeliveryFilter);
                  setCurrentPage(1);
                }}
                className="btn btn-secondary"
                style={{ borderRadius: 10, padding: "8px 12px" }}
                aria-label="Delivery filter"
              >
                <option value="All">All Leads</option>
                <option value="Available">Available</option>
                <option value="Delivered">Delivered</option>
              </select>
            </div>
          </div>

          {loading ? (
            <div className="metric-note">Loading leads...</div>
          ) : leads.length === 0 ? (
            <div className="metric-note">No leads available</div>
          ) : (
            leads.map((lead) => {
              const stage = statusByLeadId[lead.id] ?? lead.stage;

              return (
                <button
                  key={lead.id}
                  type="button"
                  className="lead-row"
                  style={{
                    width: "100%",
                    background: selectedLeadId === lead.id ? "#f8fbff" : "#fff",
                    border: 0,
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                  onClick={() => setSelectedLeadId(lead.id)}
                >
                  <div className="lead-main">
                    <div className="avatar">{lead.initials}</div>
                    <div className="lead-text">
                      <div className="lead-name">
                        {lead.name}
                        <span style={{ color: "#64748b", fontSize: 13 }}>
                          • {lead.state}
                        </span>
                        <span
                          className="badge"
                          style={{
                            background: lead.isDownloaded ? "#e2e8f0" : "#dcfce7",
                            color: lead.isDownloaded ? "#334155" : "#166534",
                          }}
                        >
                          {lead.isDownloaded ? "Delivered" : "Available"}
                        </span>
                        {stage !== "New" ? (
                          <span className={stageClassName(stage)}>{stage}</span>
                        ) : null}
                      </div>
                      <div className="lead-sub">
                        {lead.headline} • <strong>{lead.assets}</strong>
                      </div>
                    </div>
                  </div>
                  <div className="lead-time">{lead.dateTime}</div>
                </button>
              );
            })
          )}

          <div
            className="row"
            style={{ justifyContent: "space-between", marginTop: 12 }}
          >
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || currentPage <= 1}
              onClick={() => setCurrentPage((previous) => Math.max(1, previous - 1))}
            >
              Previous
            </button>
            <span className="metric-note">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || currentPage >= totalPages}
              onClick={() =>
                setCurrentPage((previous) =>
                  Math.min(totalPages, previous + 1),
                )
              }
            >
              Next
            </button>
          </div>
        </article>

        <aside className="panel stack">
          {!selectedLead ? (
            <p>Select a lead to see details.</p>
          ) : (
            <>
              <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>
                Lead Details
              </h2>
              <h3
                style={{ margin: "4px 0 0 0", fontSize: 32, color: "#0b1b49" }}
              >
                {selectedLead.name}
              </h3>
              <p style={{ margin: 0, color: "#475569" }}>
                {selectedLead.headline}
              </p>

              <div style={{ display: "grid", gap: 8 }}>
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span>State</span>
                  <strong>{selectedLead.state}</strong>
                </div>
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span>Assets</span>
                  <strong>{selectedLead.assets}</strong>
                </div>
                <div
                  style={{ display: "flex", justifyContent: "space-between" }}
                >
                  <span>Phone</span>
                  <strong>{selectedLead.phone}</strong>
                </div>
              </div>
              {!selectedLead.piiUnlocked ? (
                <p className="metric-note" style={{ margin: 0 }}>
                  Contact details are available after delivery.
                </p>
              ) : null}

              <div className="field">
                <label htmlFor="lead-status">Update Status</label>
                <select
                  id="lead-status"
                  value={selectedStatus}
                  onChange={(event) => {
                    const next = event.target.value as LeadStage;
                    setStatusByLeadId((previous) => ({
                      ...previous,
                      [selectedLead.id]: next,
                    }));
                  }}
                >
                  {STAGES.map((stage) => (
                    <option key={stage} value={stage}>
                      {stage}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="lead-notes">Notes</label>
                <textarea
                  id="lead-notes"
                  value={selectedNotes}
                  onChange={(event) => {
                    setNotesByLeadId((previous) => ({
                      ...previous,
                      [selectedLead.id]: event.target.value.slice(0, 2000),
                    }));
                  }}
                  maxLength={2000}
                  placeholder="Add call notes, appointment time, objections, etc."
                />
              </div>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void handleSave()}
                disabled={saving}
              >
                {saving ? "Saving..." : "Save"}
              </button>
            </>
          )}
        </aside>
      </section>
    </div>
  );
};

export default LeadsPage;
