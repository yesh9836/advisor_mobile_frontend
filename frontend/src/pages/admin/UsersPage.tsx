import type { CSSProperties } from "react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getUsers } from "@/api/admin";
import type { AdminUserListItem, UserListFilters } from "@/types/admin";
import { getApiErrorMessage } from "@/utils/api-error";

const DEFAULT_PAGE_SIZE = 20;

interface UserFilterDraft {
  search: string;
  role: "" | "admin" | "advisor";
  status: "" | "active" | "inactive";
}

const defaultDraftFilters: UserFilterDraft = {
  search: "",
  role: "",
  status: "",
};

const toApiFilters = (draft: UserFilterDraft): UserListFilters => {
  const trimmedSearch = draft.search.trim();
  return {
    search: trimmedSearch || undefined,
    role: draft.role || undefined,
    status: draft.status || undefined,
  };
};

const formatDateTime = (isoTimestamp: string): string => {
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

const formatRole = (role: string): string =>
  role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();

const formatCreditSummary = (credits: number, purchases: number): string => {
  if (purchases <= 0) return "No purchases";
  const purchaseLabel = purchases === 1 ? "purchase" : "purchases";
  return `${credits} credits • ${purchases} ${purchaseLabel}`;
};

const statusBadgeStyle = (isActive: boolean): CSSProperties => {
  if (isActive) {
    return {
      border: "1px solid #bbf7d0",
      background: "#ecfdf3",
      color: "#047857",
    };
  }

  return {
    border: "1px solid #fecaca",
    background: "#fef2f2",
    color: "#b91c1c",
  };
};

const UsersPage = () => {
  const navigate = useNavigate();

  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState(DEFAULT_PAGE_SIZE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterDraft, setFilterDraft] = useState<UserFilterDraft>(defaultDraftFilters);
  const [filters, setFilters] = useState<UserListFilters>({});

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / size)),
    [total, size],
  );

  useEffect(() => {
    let cancelled = false;

    const loadUsers = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await getUsers(page, size, filters);
        if (cancelled) return;
        setUsers(response.items);
        setTotal(response.total);
      } catch (loadError) {
        if (cancelled) return;
        setUsers([]);
        setTotal(0);
        setError(getApiErrorMessage(loadError, "Unable to load users."));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadUsers();

    return () => {
      cancelled = true;
    };
  }, [filters, page, size]);

  const handleApplyFilters = () => {
    setPage(1);
    setFilters(toApiFilters(filterDraft));
  };

  const handleResetFilters = () => {
    setFilterDraft(defaultDraftFilters);
    setFilters({});
    setPage(1);
  };

  return (
    <div className="page">
      <div className="page-header-row">
        <div>
          <h1>Admin • Users</h1>
          <p className="page-subtitle">
            Search and manage platform users with role and status controls.
          </p>
        </div>
      </div>

      {error && <div className="alert">{error}</div>}

      <section className="panel stack">
        <div>
          <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>Filters</h2>
        </div>

        <div className="grid-3">
          <div className="field">
            <label htmlFor="users-search">Search</label>
            <input
              id="users-search"
              value={filterDraft.search}
              onChange={(event) =>
                setFilterDraft((prev) => ({ ...prev, search: event.target.value }))
              }
              placeholder="Name or email"
            />
          </div>

          <div className="field">
            <label htmlFor="users-role">Role</label>
            <select
              id="users-role"
              value={filterDraft.role}
              onChange={(event) =>
                setFilterDraft((prev) => ({
                  ...prev,
                  role: event.target.value as UserFilterDraft["role"],
                }))
              }
            >
              <option value="">All roles</option>
              <option value="advisor">Advisor</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="field">
            <label htmlFor="users-status">Status</label>
            <select
              id="users-status"
              value={filterDraft.status}
              onChange={(event) =>
                setFilterDraft((prev) => ({
                  ...prev,
                  status: event.target.value as UserFilterDraft["status"],
                }))
              }
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
        </div>

        <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
          <div className="field" style={{ minWidth: 140 }}>
            <label htmlFor="users-page-size">Rows per page</label>
            <select
              id="users-page-size"
              value={size}
              onChange={(event) => {
                setPage(1);
                setSize(Number(event.target.value));
              }}
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>

          <div className="row" style={{ alignItems: "flex-end" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleResetFilters}
              disabled={loading}
            >
              Reset
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleApplyFilters}
              disabled={loading}
            >
              Apply Filters
            </button>
          </div>
        </div>
      </section>

      <section className="panel stack">
        <div>
          <h2 style={{ margin: 0, fontSize: 30, color: "#0b1b49" }}>User Directory</h2>
          <p style={{ margin: "4px 0 0 0", color: "#475569" }}>
            Click a row to view user details and administrative history.
          </p>
        </div>

        <div style={{ overflowX: "auto", border: "1px solid #dbe4f0", borderRadius: 12 }}>
          <table className="min-w-full bg-white text-left text-sm">
            <thead style={{ background: "#f8fafc", color: "#1f3a6b" }}>
              <tr>
                <th style={{ padding: "12px 14px" }}>Name</th>
                <th style={{ padding: "12px 14px" }}>Email</th>
                <th style={{ padding: "12px 14px" }}>Role</th>
                <th style={{ padding: "12px 14px" }}>Status</th>
                <th style={{ padding: "12px 14px" }}>Licenses</th>
                <th style={{ padding: "12px 14px" }}>Credits</th>
                <th style={{ padding: "12px 14px" }}>Created</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: 24, color: "#475569", textAlign: "center" }}>
                    Loading users...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: 24, color: "#475569", textAlign: "center" }}>
                    No users found for the selected filters.
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr
                    key={user.id}
                    tabIndex={0}
                    role="button"
                    onClick={() => navigate(`/admin/users/${user.id}`)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        navigate(`/admin/users/${user.id}`);
                      }
                    }}
                    style={{
                      borderTop: "1px solid #e2e8f0",
                      cursor: "pointer",
                    }}
                    aria-label={`View details for ${user.name}`}
                  >
                    <td style={{ padding: "12px 14px", color: "#0b1b49", fontWeight: 700 }}>
                      {user.name}
                    </td>
                    <td style={{ padding: "12px 14px", color: "#334155" }}>{user.email}</td>
                    <td style={{ padding: "12px 14px", color: "#334155" }}>
                      {formatRole(user.role)}
                    </td>
                    <td style={{ padding: "12px 14px" }}>
                      <span
                        style={{
                          borderRadius: 999,
                          padding: "3px 10px",
                          fontSize: 12,
                          fontWeight: 700,
                          ...statusBadgeStyle(user.is_active),
                        }}
                      >
                        {user.is_active ? "ACTIVE" : "INACTIVE"}
                      </span>
                    </td>
                    <td style={{ padding: "12px 14px", color: "#334155" }}>
                      {user.license_count}
                    </td>
                    <td style={{ padding: "12px 14px", color: "#334155" }}>
                      {formatCreditSummary(user.current_credits, user.total_purchases)}
                    </td>
                    <td style={{ padding: "12px 14px", color: "#475569" }}>
                      {formatDateTime(user.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ color: "#475569", fontSize: 14 }}>
            Page {page} of {totalPages} • {total} total users
          </span>

          <div className="row">
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || page <= 1}
              onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            >
              Previous
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading || page >= totalPages}
              onClick={() => setPage((prev) => prev + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};

export default UsersPage;
