import { useMemo, type ReactNode } from "react";

import Button from "@/components/common/Button";

export interface TableColumn<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
}

interface TablePagination {
  page: number;
  size: number;
  total: number;
  onPageChange: (nextPage: number) => void;
  onPageSizeChange?: (nextSize: number) => void;
  pageSizeOptions?: number[];
}

interface TableProps<T> {
  columns: TableColumn<T>[];
  data: T[];
  loading?: boolean;
  rowKey?: (row: T, index: number) => string | number;
  emptyMessage?: string;
  pagination?: TablePagination;
  className?: string;
}

const DEFAULT_PAGE_SIZES = [10, 20, 50];

const cn = (...classes: Array<string | false | null | undefined>): string =>
  classes.filter(Boolean).join(" ");

const Table = <T,>({
  columns,
  data,
  loading = false,
  rowKey,
  emptyMessage = "No records found",
  pagination,
  className,
}: TableProps<T>) => {
  const totalPages = useMemo(() => {
    if (!pagination) {
      return 1;
    }

    return Math.max(1, Math.ceil(pagination.total / pagination.size));
  }, [pagination]);

  const showingFrom = pagination
    ? pagination.total === 0
      ? 0
      : (pagination.page - 1) * pagination.size + 1
    : 0;

  const showingTo = pagination
    ? Math.min(pagination.total, pagination.page * pagination.size)
    : 0;

  return (
    <div className={cn("space-y-4", className)}>
      <div className="overflow-x-auto rounded-2xl border border-[#d9e4f8]">
        <table className="min-w-full bg-white text-left text-sm">
          <thead className="bg-[#f8fbff] text-xs uppercase tracking-wide text-[#4c628a]">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={cn(
                    "px-4 py-3 font-semibold",
                    column.headerClassName,
                  )}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {loading ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-[#4c628a]"
                >
                  Loading...
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-[#4c628a]"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((row, index) => (
                <tr
                  key={rowKey ? rowKey(row, index) : index}
                  className="border-t border-[#e7eefc] text-[#0a1633]"
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn("px-4 py-3", column.className)}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination && (
        <div className="flex flex-col items-start justify-between gap-3 rounded-2xl border border-[#d9e4f8] bg-white p-3 text-sm text-[#4c628a] sm:flex-row sm:items-center">
          <div>
            Showing {showingFrom} to {showingTo} of {pagination.total}
          </div>

          <div className="flex items-center gap-2">
            {pagination.onPageSizeChange && (
              <select
                value={pagination.size}
                onChange={(event) =>
                  pagination.onPageSizeChange?.(Number(event.target.value))
                }
                className="rounded-full border border-[#d9e4f8] px-3 py-1.5 text-sm text-[#0a1633] focus:border-[#8ea4d8] focus:outline-none"
                aria-label="Rows per page"
              >
                {(pagination.pageSizeOptions ?? DEFAULT_PAGE_SIZES).map(
                  (size) => (
                    <option key={size} value={size}>
                      {size}/page
                    </option>
                  ),
                )}
              </select>
            )}

            <Button
              variant="secondary"
              className="px-3 py-1.5"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
            >
              Previous
            </Button>

            <span className="px-2 text-xs font-semibold text-[#4c628a]">
              Page {pagination.page} / {totalPages}
            </span>

            <Button
              variant="secondary"
              className="px-3 py-1.5"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Table;
