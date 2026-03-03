import { describe, expect, it } from "vitest";

import { normalizeQueryParams } from "@/api/query-params";
import type { LeadFilters } from "@/types/lead";

describe("normalizeQueryParams", () => {
  it("trims non-empty strings and removes nullish/blank values", () => {
    expect(
      normalizeQueryParams({
        search: "  alpha  ",
        status: "   ",
        optional: undefined,
        deleted: null,
        state: " NY ",
      }),
    ).toEqual({
      search: "alpha",
      state: "NY",
    });
  });

  it("keeps number and boolean values without coercion", () => {
    expect(
      normalizeQueryParams({
        page: 2,
        size: 25,
        include_archived: false,
      }),
    ).toEqual({
      page: 2,
      size: 25,
      include_archived: false,
    });
  });

  it("supports typed filter objects without index signatures", () => {
    const filters: LeadFilters = {
      search: "  jane smith  ",
      outcome_status: "contacted",
      created_from: undefined,
      state_code: " CA ",
    };

    expect(normalizeQueryParams(filters)).toEqual({
      search: "jane smith",
      outcome_status: "contacted",
      state_code: "CA",
    });
  });
});
