import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createLeadAsAdmin,
  getLeadInventory,
  getLicenseStatusSummary,
} from "@/api/admin";
import ImportModal from "@/components/admin/ImportModal";
import { toImportSummary } from "@/components/admin/import-summary";
import type {
  AdminLeadInventoryItem,
  LeadInventoryFilters,
  LicenseStatusSummaryItem,
} from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const PAGE_SIZE = 20;

const formatLeadName = (lead: AdminLeadInventoryItem): string => {
  const fullName = `${lead.first_name ?? ""} ${lead.last_name ?? ""}`.trim();
  return fullName || "Unknown Name";
};

const formatLeadTimestamp = (isoTimestamp: string): string => {
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

const formatSourceLabel = (source: string | null): string => {
  if (!source) return "unknown";
  return source.replace(/_/g, " ");
};

const statusBadgeStyle = (isSold: boolean) => {
  if (isSold) {
    return {
      border: "1px solid #fde68a",
      background: "#fffbeb",
      color: "#b45309",
    };
  }

  return {
    border: "1px solid #bbf7d0",
    background: "#ecfdf3",
    color: "#047857",
  };
};

const defaultFilters: LeadInventoryFilters = {
  search: "",
  state_code: "",
  source: "",
  delivery_status: "all",
};

const statusOrder: Array<LicenseStatusSummaryItem["status"]> = [
  "pending",
  "verified",
  "rejected",
];

const LeadInventoryPage = () => {
  const [items, setItems] = useState<AdminLeadInventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterDraft, setFilterDraft] = useState<LeadInventoryFilters>(defaultFilters);
  const [filters, setFilters] = useState<LeadInventoryFilters>(defaultFilters);

  const [licenseSummary, setLicenseSummary] = useState<LicenseStatusSummaryItem[]>([]);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    state_code: "",
    mobile_phone: "",
    first_name: "",
    last_name: "",
    source: "manual_entry",
  });

  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importSuccess, setImportSuccess] = useState<string | null>(null);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [leadResponse, licenseResponse] = await Promise.all([
        getLeadInventory(page, PAGE_SIZE, filters),
        getLicenseStatusSummary(),
      ]);
      setItems(leadResponse.items);
      setTotal(leadResponse.total);

      const byStatus = new Map(
        licenseResponse.map((entry) => [entry.status, entry]),
      );
      setLicenseSummary(
        statusOrder.map((status) => byStatus.get(status) ?? { status, count: 0 }),
      );
    } catch (loadError) {
      setItems([]);
      setTotal(0);
      setLicenseSummary(
        statusOrder.map((status) => ({ status, count: 0 })),
      );
      setError(getApiErrorMessage(loadError, "Unable to load lead inventory."));
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    void loadInventory();
  }, [loadInventory]);

  const handleApplyFilters = () => {
    setPage(1);
    setFilters({
      search: filterDraft.search,
      state_code: filterDraft.state_code,
      source: filterDraft.source,
      delivery_status: filterDraft.delivery_status,
    });
  };

  const handleResetFilters = () => {
    setFilterDraft(defaultFilters);
    setPage(1);
    setFilters(defaultFilters);
  };

  const handleCreateLead = async () => {
    if (!createForm.state_code.trim() || !createForm.mobile_phone.trim()) {
      setCreateError("State and mobile phone are required.");
      return;
    }

    setCreateSubmitting(true);
    setCreateError(null);
    setCreateSuccess(null);

    try {
      await createLeadAsAdmin({
        state_code: createForm.state_code,
        mobile_phone: createForm.mobile_phone,
        first_name: createForm.first_name,
        last_name: createForm.last_name,
        source: createForm.source,
      });

      setCreateSuccess("Lead created successfully.");
      setCreateForm((prev) => ({
        ...prev,
        state_code: "",
        mobile_phone: "",
        first_name: "",
        last_name: "",
      }));
      setPage(1);
      if (page === 1) {
        await loadInventory();
      }
    } catch (submitError) {
      setCreateError(getApiErrorMessage(submitError, "Failed to create lead."));
    } finally {
      setCreateSubmitting(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • Lead Inventory</h1>
          <p className="page-subtitle">
            Manage lead supply, filter inventory, and track fulfillment readiness.
          </p>
        </div>

        <div className="row" style={{ flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setShowCreateForm((value) => !value)}
          >
            {showCreateForm ? "Hide Add Lead" : "Add Lead"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setImportModalOpen(true)}
          >
            Import Leads
          </button>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}
      {importSuccess && <div className="success">{importSuccess}</div>}

      {showCreateForm && (
        <section className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>Add Lead</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Create a single lead entry directly from admin inventory.
            </p>
          </div>

          {createError && <div className="alert">{createError}</div>}
          {createSuccess && <div className="success">{createSuccess}</div>}

          <div className="grid-3">
            <div className="field">
              <label htmlFor="lead-state">State</label>
              <input
                id="lead-state"
                value={createForm.state_code}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, state_code: event.target.value }))
                }
                placeholder="CA"
                maxLength={2}
              />
            </div>

            <div className="field">
              <label htmlFor="lead-phone">Mobile Phone</label>
              <input
                id="lead-phone"
                value={createForm.mobile_phone}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, mobile_phone: event.target.value }))
                }
                placeholder="555-123-4567"
              />
            </div>

            <div className="field">
              <label htmlFor="lead-source">Source</label>
              <select
                id="lead-source"
                value={createForm.source}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, source: event.target.value }))
                }
              >
                <option value="manual_entry">Manual Entry</option>
                <option value="csv_import">CSV Import</option>
                <option value="wordpress_import">WordPress Import</option>
                <option value="api_submission">API Submission</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="lead-first-name">First Name</label>
              <input
                id="lead-first-name"
                value={createForm.first_name}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, first_name: event.target.value }))
                }
                placeholder="Alex"
              />
            </div>

            <div className="field">
              <label htmlFor="lead-last-name">Last Name</label>
              <input
                id="lead-last-name"
                value={createForm.last_name}
                onChange={(event) =>
                  setCreateForm((prev) => ({ ...prev, last_name: event.target.value }))
                }
                placeholder="Parker"
              />
            </div>
          </div>

          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void handleCreateLead()}
              disabled={createSubmitting}
            >
              {createSubmitting ? "Creating..." : "Create Lead"}
            </button>
          </div>
        </section>
      )}

      <section className="grid-main">
        <article className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Inventory List</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Single source of truth for all admin lead records.
            </p>
          </div>

          <section className="panel stack" style={{ background: "#f8fafc" }}>
            <div className="grid-3">
              <div className="field">
                <label htmlFor="inventory-search">Search</label>
                <input
                  id="inventory-search"
                  value={filterDraft.search ?? ""}
                  onChange={(event) =>
                    setFilterDraft((prev) => ({ ...prev, search: event.target.value }))
                  }
                  placeholder="Name, phone, state, source"
                />
              </div>

              <div className="field">
                <label htmlFor="inventory-state">State</label>
                <input
                  id="inventory-state"
                  value={filterDraft.state_code ?? ""}
                  onChange={(event) =>
                    setFilterDraft((prev) => ({ ...prev, state_code: event.target.value }))
                  }
                  placeholder="CA"
                  maxLength={2}
                />
              </div>

              <div className="field">
                <label htmlFor="inventory-source">Source</label>
                <input
                  id="inventory-source"
                  value={filterDraft.source ?? ""}
                  onChange={(event) =>
                    setFilterDraft((prev) => ({ ...prev, source: event.target.value }))
                  }
                  placeholder="manual_entry"
                />
              </div>

              <div className="field">
                <label htmlFor="inventory-delivery-status">Delivery Status</label>
                <select
                  id="inventory-delivery-status"
                  value={filterDraft.delivery_status ?? "all"}
                  onChange={(event) =>
                    setFilterDraft((prev) => ({
                      ...prev,
                      delivery_status: event.target.value as LeadInventoryFilters["delivery_status"],
                    }))
                  }
                >
                  <option value="all">All</option>
                  <option value="unsold">Unsold</option>
                  <option value="sold">Sold</option>
                </select>
              </div>
            </div>

            <div className="row" style={{ justifyContent: "flex-end" }}>
              <button type="button" className="btn btn-secondary" onClick={handleResetFilters}>
                Reset
              </button>
              <button type="button" className="btn btn-primary" onClick={handleApplyFilters}>
                Apply Filters
              </button>
            </div>
          </section>

          {loading && <div style={{ color: "#475569" }}>Loading lead inventory...</div>}

          {!loading && items.length === 0 && (
            <div style={{ color: "#475569" }}>No leads found for current filters.</div>
          )}

          {!loading && items.map((lead) => {
            const isSold = lead.assigned_advisor_id !== null || lead.download_count > 0;
            const assignedAdvisorLabel = lead.assigned_advisor_name
              ? `${lead.assigned_advisor_name}${lead.assigned_advisor_email ? ` (${lead.assigned_advisor_email})` : ""}`
              : null;

            return (
              <section
                key={lead.id}
                className="panel"
                style={{
                  background: "#f8fafc",
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 12,
                  alignItems: "center",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: "#0b1b49", fontSize: 18, fontWeight: 700 }}>
                    {formatLeadName(lead)}
                  </div>
                  <div style={{ marginTop: 4, color: "#475569", fontSize: 14 }}>
                    {lead.state_code} • {lead.mobile_phone || "No phone"} • {formatSourceLabel(lead.source)}
                  </div>
                  <div style={{ marginTop: 4, color: "#64748b", fontSize: 13 }}>
                    Created {formatLeadTimestamp(lead.created_at)}
                  </div>
                  <div style={{ marginTop: 4, color: "#64748b", fontSize: 13 }}>
                    Assigned: {assignedAdvisorLabel ?? "Unassigned"}
                  </div>
                  <div style={{ marginTop: 4, color: "#64748b", fontSize: 13 }}>
                    Purchase: {lead.purchase_reference ?? "N/A"}
                  </div>
                </div>

                <div style={{ textAlign: "right" }}>
                  <span
                    style={{
                      borderRadius: 999,
                      padding: "4px 10px",
                      fontSize: 12,
                      fontWeight: 700,
                      ...statusBadgeStyle(isSold),
                    }}
                  >
                    {isSold ? "SOLD" : "UNSOLD"}
                  </span>
                  <div style={{ marginTop: 6, color: "#475569", fontSize: 13 }}>
                    Downloads: {lead.download_count}
                  </div>
                </div>
              </section>
            );
          })}

          <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ color: "#475569", fontSize: 14 }}>
              Page {page} of {totalPages} • {total} total leads
            </span>
            <div className="row">
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page <= 1 || loading}
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((prev) => prev + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </article>

        <aside className="panel stack">
          <div>
            <h2 style={{ margin: 0, fontSize: 28, color: "#0b1b49" }}>License Status</h2>
            <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
              Snapshot of advisor license verification queue.
            </p>
          </div>

          {licenseSummary.map((entry) => (
            <section key={entry.status} className="panel" style={{ background: "#f8fafc" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "#334155", textTransform: "capitalize", fontWeight: 700 }}>
                  {entry.status}
                </span>
                <strong style={{ color: "#0b1b49" }}>{entry.count}</strong>
              </div>
            </section>
          ))}
        </aside>
      </section>

      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportSuccess={(result) => {
          const summary = toImportSummary(result);
          setImportSuccess(
            `Import completed. Inserted ${summary.inserted} leads, ${summary.duplicateCount} duplicates, ${summary.failed} failed rows.`,
          );
          setPage(1);
          if (page === 1) {
            void loadInventory();
          }
        }}
      />
    </div>
  );
};

export default LeadInventoryPage;
