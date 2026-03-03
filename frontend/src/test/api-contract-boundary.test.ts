import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  AUTH_LOGOUT_EVENT: "auth:logout",
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
  },
}));

import apiClient from "@/api/client";
import { getDashboardStats } from "@/api/admin";
import { getCurrentUser } from "@/api/auth";
import { getMyDeliverySettings } from "@/api/delivery-settings";
import { getLeads } from "@/api/leads";
import { getMyLicenses } from "@/api/licenses";
import { getPackages } from "@/api/purchases";

type MockFn = ReturnType<typeof vi.fn>;

const mockedApiClient = apiClient as unknown as {
  get: MockFn;
  post: MockFn;
  put: MockFn;
  patch: MockFn;
};

const buildValidLeadItem = () => ({
  id: 101,
  source: "manual_entry",
  state_code: "CA",
  zip_code: null,
  first_name: "Alex",
  last_name: "Lead",
  mobile_phone: "555-0111",
  preferred_follow_up_method: null,
  best_time_to_reach: null,
  retirement_timeline: null,
  confidence_in_long_term_plan: null,
  most_important_retirement_activity: null,
  planning_to_relocate_retirement: null,
  expected_retirement_income_source: null,
  overall_health: null,
  money_management_style: null,
  investor_profile_statement: null,
  investment_comfort_level: null,
  main_purpose_for_investing: null,
  retirement_savings_range: null,
  annual_household_income_range: null,
  total_investable_assets_range: null,
  monthly_savings_range: null,
  wants_to_improve_strategy_timing: null,
  current_investment_strategies: null,
  has_financial_advisor: null,
  advisor_local_preference: null,
  owns_annuity: null,
  additional_notes: null,
  created_at: "2026-02-20T00:00:00Z",
});

describe("API contract boundary guards", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.post.mockReset();
    mockedApiClient.patch.mockReset();
    mockedApiClient.put.mockReset();
  });

  it("rejects malformed auth payloads at /auth/me", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        email: "advisor@example.com",
      },
    });

    await expect(getCurrentUser()).rejects.toThrow(
      "Unexpected response format from /auth/me",
    );
  });

  it("rejects auth payloads with unsupported role values", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        id: 1,
        email: "advisor@example.com",
        name: "Advisor",
        phone: null,
        role: "manager",
        stripe_customer_id: null,
        created_at: "2026-02-20T00:00:00Z",
      },
    });

    await expect(getCurrentUser()).rejects.toThrow(
      "Unexpected response format from /auth/me",
    );
  });

  it("rejects malformed admin dashboard payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        total_users: 8,
      },
    });

    await expect(getDashboardStats()).rejects.toThrow(
      "Unexpected response format from /admin/dashboard",
    );
  });

  it("parses valid purchase package payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          name: "Starter",
          price_cents: 20000,
          currency: "USD",
          state_limit: 2,
          daily_download_limit: 10,
          features: ["10 leads"],
          stripe_price_id: "price_starter",
          created_at: "2026-02-20T00:00:00Z",
        },
      ],
    });

    await expect(getPackages()).resolves.toEqual([
      {
        id: 1,
        name: "Starter",
        price_cents: 20000,
        currency: "USD",
        state_limit: 2,
        daily_download_limit: 10,
        features: ["10 leads"],
        stripe_price_id: "price_starter",
        created_at: "2026-02-20T00:00:00Z",
      },
    ]);
  });

  it("rejects malformed lead collection payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: {},
        total: 0,
        page: 1,
        size: 25,
      },
    });

    await expect(getLeads(1, 25)).rejects.toThrow(
      "Unexpected response format from /leads/",
    );
  });

  it("rejects leads payloads when source is missing", async () => {
    const itemWithoutSource = buildValidLeadItem() as {
      source?: string | null;
      [key: string]: unknown;
    };
    delete itemWithoutSource.source;

    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [itemWithoutSource],
        total: 1,
        page: 1,
        size: 25,
      },
    });

    await expect(getLeads(1, 25)).rejects.toThrow(/source/);
  });

  it("requests the canonical /leads/ path and normalized filters", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        items: [buildValidLeadItem()],
        total: 1,
        page: 2,
        size: 25,
      },
    });

    await expect(
      getLeads(2, 25, {
        search: "  alex  ",
        state_code: " NY ",
        delivery_status: "all",
      }),
    ).resolves.toBeDefined();

    expect(mockedApiClient.get).toHaveBeenCalledWith("/leads/", {
      params: {
        page: 2,
        size: 25,
        search: "alex",
        state_code: "NY",
        delivery_status: "all",
      },
    });
  });

  it("rejects malformed licenses payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 7,
          user_id: 2,
          state: "CA",
          license_number: "CA-123",
          license_type: null,
          verification_status: "pending",
          verified_at: null,
          verified_by: null,
          rejection_reason: null,
          created_at: "2026-02-20T00:00:00Z",
        },
      ],
    });

    await expect(getMyLicenses()).rejects.toThrow(
      "Unexpected response format from /licenses",
    );
  });

  it("rejects malformed delivery settings payloads", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        email_alerts_enabled: true,
        sms_alerts_enabled: false,
        version: 4,
        updated_at: "2026-02-20T00:00:00Z",
        warnings: "none",
      },
    });

    await expect(getMyDeliverySettings()).rejects.toThrow(
      "Unexpected response format from /delivery-settings/me",
    );
  });
});
