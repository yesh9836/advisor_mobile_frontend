import type { LeadBulkImportResult } from "@/types/admin";

export interface ImportSummary {
  inserted: number;
  failed: number;
  duplicateCount: number;
}

const countDuplicates = (result: LeadBulkImportResult): number => {
  return result.errors.filter((entry) =>
    entry.error.toLowerCase().includes("duplicate"),
  ).length;
};

export const toImportSummary = (result: LeadBulkImportResult): ImportSummary => {
  return {
    inserted: result.success,
    failed: result.failed,
    duplicateCount: countDuplicates(result),
  };
};
