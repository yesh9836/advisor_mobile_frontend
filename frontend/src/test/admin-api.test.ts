import { beforeEach, describe, expect, it, vi } from "vitest";

import apiClient from "@/api/client";
import * as adminApi from "@/api/admin";
import {
  archiveAdminPlan,
  approveLicense,
  bulkImportLeadsAsAdmin,
  createAdminPlan,
  createLeadAsAdmin,
  deactivateAdminUser,
  deactivateUser,
  downloadOrdersExport,
  downloadLicenseDocument,
  getAnalyticsOverview,
  getAdminAuditLogs,
  getAdminDashboardStats,
  getAdminPlans,
  getAdminUserDetails,
  getAdminUsers,
  getAuditLogs,
  getDashboardStats,
  getLeadBulkImportSchemaAsAdmin,
  getLeadInventory,
  getLicenseStatusSummary,
  getOrders,
  getPendingLicenses,
  getProcessedLicenses,
  getUserDownloadHistory,
  getUserLicenses,
  getUserPurchaseHistory,
  getUserRecentActivity,
  getUser,
  getUsers,
  previewLicenseDocument,
  rejectLicense,
  unarchiveAdminPlan,
  updateAdminPlan,
} from "@/api/admin";

vi.mock("@/api/client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
  },
}));

type MockFn = ReturnType<typeof vi.fn>;

const mockedApiClient = apiClient as unknown as {
  get: MockFn;
  post: MockFn;
  put: MockFn;
};

const buildDashboardStats = () => ({
  total_users: 9,
  completed_purchases: 4,
  advisors_with_credits: 3,
  pending_licenses: 2,
  total_leads: 120,
  total_revenue_cents: 450000,
  currency: "USD",
});

const buildAdminUserDetails = () => ({
  id: 14,
  name: "Jane Advisor",
  email: "jane.advisor@example.com",
  role: "advisor",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  deactivated_at: null,
  deactivated_by: null,
  credit_summary: {
    total_credits: 10,
    remaining_credits: 4,
    completed_purchases: 2,
  },
  licenses_preview: {
    items: [],
    total: 0,
    has_more: false,
  },
  purchase_history_preview: {
    items: [],
    total: 0,
    has_more: false,
  },
  download_history_preview: {
    items: [],
    total: 0,
    has_more: false,
  },
  recent_activity_preview: {
    items: [],
    total: 0,
    has_more: false,
  },
});

const buildLicense = (id: number) => ({
  id,
  user_id: 7,
  state: "CA",
  license_number: "CA-123",
  license_type: null,
  has_document: true,
  verification_status: "pending" as const,
  verified_at: null,
  verified_by: null,
  rejection_reason: null,
  created_at: "2026-02-20T00:00:00Z",
});

describe("admin API contract", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.post.mockReset();
    mockedApiClient.put.mockReset();
  });

  it("does not expose removed WordPress sync endpoint", () => {
    expect("syncWordPress" in adminApi).toBe(false);
  });

  it("getDashboardStats uses GET /admin/dashboard", async () => {
    const dashboard = buildDashboardStats();
    mockedApiClient.get.mockResolvedValueOnce({ data: dashboard });

    await expect(getDashboardStats()).resolves.toEqual(dashboard);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/dashboard");
  });

  it("getAnalyticsOverview uses GET /admin/analytics", async () => {
    const payload = {
      monthly_revenue: [],
      plan_breakdown: [],
      state_distribution: [],
      user_growth: [],
    };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getAnalyticsOverview()).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/analytics");
  });

  it("getAdminPlans sends normalized filters", async () => {
    const payload = {
      items: [],
      total: 0,
      page: 1,
      size: 20,
    };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(
      getAdminPlans(1, 20, {
        search: "  Growth  ",
        archived: "unarchived",
        effective_at: "2026-02-26T12:00:00Z",
      }),
    ).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/plans", {
      params: {
        page: 1,
        size: 20,
        search: "Growth",
        archived: "unarchived",
        effective_at: "2026-02-26T12:00:00Z",
      },
    });
  });

  it("create/update/archive/unarchive plan calls use admin plan endpoints", async () => {
    const plan = {
      id: 19,
      name: "Growth 25",
      price_cents: 25000,
      currency: "USD",
      stripe_product_id: "prod_growth_25",
      stripe_price_id: "price_growth_25",
      state_limit: 3,
      credits_total: 25,
      catalog_visible: true,
      is_archived: false,
      archived_at: null,
      effective_from: null,
      effective_to: null,
      created_at: "2026-02-26T12:00:00Z",
      updated_at: "2026-02-26T12:10:00Z",
      updated_by: 1,
      has_purchases: false,
    };
    mockedApiClient.post.mockResolvedValueOnce({ data: plan });
    mockedApiClient.put.mockResolvedValueOnce({ data: { ...plan, name: "Growth 30", credits_total: 30 } });
    mockedApiClient.post.mockResolvedValueOnce({ data: { ...plan, is_archived: true, archived_at: "2026-02-26T12:20:00Z" } });
    mockedApiClient.post.mockResolvedValueOnce({ data: plan });

    await expect(
      createAdminPlan({
        name: "  Growth 25  ",
        price_cents: 25000,
        credits_total: 25,
        state_limit: 3,
        catalog_visible: true,
        effective_from: null,
        effective_to: null,
        request_id: "  plan_create_01  ",
      }),
    ).resolves.toEqual(plan);

    await expect(
      updateAdminPlan(19, {
        name: " Growth 30 ",
        credits_total: 30,
        price_cents: 30000,
        request_id: " plan_update_01 ",
      }),
    ).resolves.toEqual({ ...plan, name: "Growth 30", credits_total: 30 });

    await expect(archiveAdminPlan(19, " retire ")).resolves.toEqual({
      ...plan,
      is_archived: true,
      archived_at: "2026-02-26T12:20:00Z",
    });
    await expect(unarchiveAdminPlan(19, " restore ")).resolves.toEqual(plan);

    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      1,
      "/admin/plans",
      {
        name: "Growth 25",
        price_cents: 25000,
        credits_total: 25,
        state_limit: 3,
        catalog_visible: true,
        effective_from: null,
        effective_to: null,
        request_id: "plan_create_01",
      },
    );
    expect(mockedApiClient.put).toHaveBeenCalledWith("/admin/plans/19", {
      name: "Growth 30",
      credits_total: 30,
      price_cents: 30000,
      request_id: "plan_update_01",
    });
    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      2,
      "/admin/plans/19/archive",
      { reason: "retire" },
    );
    expect(mockedApiClient.post).toHaveBeenNthCalledWith(
      3,
      "/admin/plans/19/unarchive",
      { reason: "restore" },
    );
  });

  it("updateAdminPlan preserves explicit nulls for clearable fields", async () => {
    const plan = {
      id: 22,
      name: "Plan 22",
      price_cents: 22000,
      currency: "USD",
      stripe_product_id: "prod_22",
      stripe_price_id: "price_22",
      state_limit: null,
      credits_total: 22,
      catalog_visible: true,
      is_archived: false,
      archived_at: null,
      effective_from: null,
      effective_to: null,
      created_at: "2026-02-26T12:00:00Z",
      updated_at: "2026-02-26T12:10:00Z",
      updated_by: 1,
      has_purchases: false,
    };
    mockedApiClient.put.mockResolvedValueOnce({ data: plan });

    await expect(
      updateAdminPlan(22, {
        state_limit: null,
        effective_from: null,
        effective_to: null,
      }),
    ).resolves.toEqual(plan);

    expect(mockedApiClient.put).toHaveBeenCalledWith("/admin/plans/22", {
      state_limit: null,
      effective_from: null,
      effective_to: null,
    });
  });

  it("getUsers sends page, size, and normalized filters", async () => {
    const users = { items: [], total: 0, page: 2, size: 25 };
    mockedApiClient.get.mockResolvedValueOnce({ data: users });

    await expect(
      getUsers(2, 25, {
        search: "  jane advisor  ",
        role: "advisor",
        status: "active",
      }),
    ).resolves.toEqual(users);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users", {
      params: {
        page: 2,
        size: 25,
        search: "jane advisor",
        role: "advisor",
        status: "active",
      },
    });
  });

  it("getUsers drops undefined and empty-string filters", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, size: 20 },
    });

    await getUsers(1, 20, { search: "   " });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users", {
      params: {
        page: 1,
        size: 20,
      },
    });
  });

  it("getOrders sends page/size and optional normalized status", async () => {
    const orders = { items: [], total: 0, page: 1, size: 20 };
    mockedApiClient.get.mockResolvedValueOnce({ data: orders });

    await expect(getOrders(1, 20, "  active ")).resolves.toEqual(orders);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/orders", {
      params: {
        page: 1,
        size: 20,
        status: "active",
      },
    });
  });

  it("downloadOrdersExport fetches blob with normalized optional status and filename", async () => {
    const blob = new Blob(["order_reference,amount_dollars\ncs_1,100.00\n"], {
      type: "text/csv",
    });
    mockedApiClient.get.mockResolvedValueOnce({
      data: blob,
      headers: {
        "content-disposition": "attachment; filename=admin_orders_20260223_103000.csv",
      },
    });

    await expect(downloadOrdersExport("  completed ")).resolves.toEqual({
      blob,
      filename: "admin_orders_20260223_103000.csv",
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/orders/export", {
      params: {
        status: "completed",
      },
      responseType: "blob",
    });
  });

  it("getLeadInventory sends pagination and normalized filters", async () => {
    const responsePayload = { items: [], total: 0, page: 1, size: 20 };
    mockedApiClient.get.mockResolvedValueOnce({ data: responsePayload });

    await expect(
      getLeadInventory(1, 20, {
        search: "  alice  ",
        state_code: " ca ",
        source: "  csv_import  ",
        delivery_status: "sold",
      }),
    ).resolves.toEqual(responsePayload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/lead-inventory", {
      params: {
        page: 1,
        size: 20,
        search: "alice",
        state_code: "CA",
        source: "csv_import",
        delivery_status: "sold",
      },
    });
  });

  it("getLicenseStatusSummary uses GET /admin/license-status-summary", async () => {
    const summary = [
      { status: "pending", count: 2 },
      { status: "verified", count: 10 },
      { status: "rejected", count: 1 },
    ];
    mockedApiClient.get.mockResolvedValueOnce({ data: summary });

    await expect(getLicenseStatusSummary()).resolves.toEqual(summary);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/license-status-summary");
  });

  it("createLeadAsAdmin posts normalized lead payload", async () => {
    const created = {
      id: 45,
      source: "manual_entry",
      state_code: "CA",
      zip_code: null,
      first_name: "Alice",
      last_name: "Lane",
      mobile_phone: "555-222-3000",
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
      updated_at: null,
      outcome_status: null,
      outcome_notes: null,
      outcome_updated_at: null,
      is_downloaded: false,
      downloaded_at: null,
    };
    mockedApiClient.post.mockResolvedValueOnce({ data: created });

    await expect(
      createLeadAsAdmin({
        state_code: " ca ",
        mobile_phone: " 555-222-3000 ",
        first_name: "  Alice ",
        last_name: "  Lane ",
        source: " manual_entry ",
      }),
    ).resolves.toEqual(created);

    expect(mockedApiClient.post).toHaveBeenCalledWith("/leads/", {
      state_code: "CA",
      mobile_phone: "555-222-3000",
      first_name: "Alice",
      last_name: "Lane",
      source: "manual_entry",
    });
  });

  it("getUser uses GET /admin/users/{id}", async () => {
    const details = buildAdminUserDetails();
    mockedApiClient.get.mockResolvedValueOnce({ data: details });

    await expect(getUser(14)).resolves.toEqual(details);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/14");
  });

  it("getUserLicenses sends page/size params", async () => {
    const payload = { items: [], total: 0, page: 1, size: 20 };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getUserLicenses(14, 1, 20)).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/14/licenses", {
      params: { page: 1, size: 20 },
    });
  });

  it("getUserPurchaseHistory sends page/size params", async () => {
    const payload = { items: [], total: 0, page: 2, size: 20 };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getUserPurchaseHistory(14, 2, 20)).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/14/purchase-history", {
      params: { page: 2, size: 20 },
    });
  });

  it("getUserDownloadHistory sends page/size params", async () => {
    const payload = { items: [], total: 0, page: 1, size: 10 };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getUserDownloadHistory(14, 1, 10)).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/14/download-history", {
      params: { page: 1, size: 10 },
    });
  });

  it("getUserRecentActivity sends page/size params", async () => {
    const payload = { items: [], total: 0, page: 3, size: 5 };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getUserRecentActivity(14, 3, 5)).resolves.toEqual(payload);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/14/recent-activity", {
      params: { page: 3, size: 5 },
    });
  });

  it("deactivateUser posts normalized reason payload and returns void", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { detail: "User deactivated" } });

    await expect(deactivateUser(27, "  Fraud review  ")).resolves.toBeUndefined();

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/admin/users/27/deactivate",
      { reason: "Fraud review" },
    );
  });

  it("deactivateUser sends empty payload when reason is blank", async () => {
    mockedApiClient.post.mockResolvedValueOnce({ data: { detail: "User deactivated" } });

    await deactivateUser(27, "   ");

    expect(mockedApiClient.post).toHaveBeenCalledWith("/admin/users/27/deactivate", {});
  });

  it("getAuditLogs sends page/size + normalized filters", async () => {
    const logs = { items: [], total: 0, page: 1, size: 20 };
    mockedApiClient.get.mockResolvedValueOnce({ data: logs });

    await expect(
      getAuditLogs(
        {
          action: "   ",
          actor_user_id: 11,
          entity_type: "User",
          entity_id: 99,
          created_from: "2026-01-01T00:00:00Z",
          created_to: "2026-02-01T00:00:00Z",
        },
        1,
        20,
      ),
    ).resolves.toEqual(logs);

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/audit-logs", {
      params: {
        page: 1,
        size: 20,
        actor_user_id: 11,
        entity_type: "User",
        entity_id: 99,
        created_from: "2026-01-01T00:00:00Z",
        created_to: "2026-02-01T00:00:00Z",
      },
    });
  });

  it("compat wrappers keep prior signatures", async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: buildDashboardStats() });
    mockedApiClient.get.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, size: 20 },
    });
    mockedApiClient.get.mockResolvedValueOnce({ data: buildAdminUserDetails() });
    mockedApiClient.get.mockResolvedValueOnce({
      data: { items: [], total: 0, page: 1, size: 20 },
    });
    mockedApiClient.post.mockResolvedValue({ data: { detail: "User deactivated" } });

    await getAdminDashboardStats();
    await getAdminUsers();
    await getAdminUserDetails(8);
    await getAdminAuditLogs({});
    const result = await deactivateAdminUser(8, { reason: " duplicate " });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/dashboard");
    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users", {
      params: { page: 1, size: 20 },
    });
    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/users/8");
    expect(mockedApiClient.get).toHaveBeenCalledWith("/admin/audit-logs", {
      params: { page: 1, size: 20 },
    });
    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/admin/users/8/deactivate",
      { reason: "duplicate" },
    );
    expect(result).toEqual({ detail: "User deactivated" });
  });

  it("bulkImportLeadsAsAdmin posts multipart form data", async () => {
    const file = new File(["a,b"], "leads.csv", { type: "text/csv" });
    const payload = { success: 10, failed: 1, errors: [{ row: 2, error: "duplicate" }] };
    mockedApiClient.post.mockResolvedValueOnce({ data: payload });

    await expect(bulkImportLeadsAsAdmin(file)).resolves.toEqual(payload);

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/leads/bulk",
      expect.any(FormData),
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
  });

  it("getLeadBulkImportSchemaAsAdmin fetches backend import schema", async () => {
    const payload = {
      headers: ["state_code", "zip_code", "mobile_phone"],
      required_values: ["state_code", "mobile_phone"],
      system_fields: { source: "csv_import" },
    };
    mockedApiClient.get.mockResolvedValueOnce({ data: payload });

    await expect(getLeadBulkImportSchemaAsAdmin()).resolves.toEqual(payload);
    expect(mockedApiClient.get).toHaveBeenCalledWith("/leads/bulk/schema");
  });

  it("license approval calls keep existing endpoint contracts", async () => {
    mockedApiClient.get.mockResolvedValueOnce({ data: [] });
    mockedApiClient.get.mockResolvedValueOnce({ data: [] });
    mockedApiClient.post.mockResolvedValueOnce({ data: buildLicense(7) });
    mockedApiClient.post.mockResolvedValueOnce({ data: buildLicense(7) });

    await getPendingLicenses();
    await getProcessedLicenses({ advisorId: 3, advisorQuery: "jane" });
    await approveLicense(7);
    await rejectLicense(7, "  Bad image  ");

    expect(mockedApiClient.get).toHaveBeenCalledWith("/licenses/pending");
    expect(mockedApiClient.get).toHaveBeenCalledWith("/licenses/processed", {
      params: {
        advisor_id: 3,
        advisor_query: "jane",
      },
    });
    expect(mockedApiClient.post).toHaveBeenCalledWith("/licenses/7/approve");
    expect(mockedApiClient.post).toHaveBeenCalledWith("/licenses/7/reject", {
      rejection_reason: "Bad image",
    });
  });

  it("downloadLicenseDocument parses filename from content-disposition", async () => {
    const blob = new Blob(["file"], { type: "application/pdf" });
    mockedApiClient.get.mockResolvedValueOnce({
      data: blob,
      headers: {
        "content-disposition": "attachment; filename=license_55.pdf",
      },
    });

    await expect(downloadLicenseDocument(55)).resolves.toEqual({
      blob,
      filename: "license_55.pdf",
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/licenses/55/document", {
      responseType: "blob",
    });
  });

  it("previewLicenseDocument sets preview query and normalizes content-type", async () => {
    const blob = new Blob(["file"], { type: "application/pdf" });
    mockedApiClient.get.mockResolvedValueOnce({
      data: blob,
      headers: {
        "content-type": "Application/PDF",
      },
    });

    await expect(previewLicenseDocument(55)).resolves.toEqual({
      blob,
      contentType: "application/pdf",
    });

    expect(mockedApiClient.get).toHaveBeenCalledWith("/licenses/55/document", {
      params: { access_mode: "preview" },
      responseType: "blob",
    });
  });

  it("propagates axios errors to callers", async () => {
    const getError = new Error("request failed");
    const postError = new Error("post failed");
    mockedApiClient.get.mockRejectedValueOnce(getError);
    mockedApiClient.post.mockRejectedValueOnce(postError);

    await expect(getUsers(1, 20)).rejects.toBe(getError);
    await expect(deactivateUser(9, "fraud")).rejects.toBe(postError);
  });
});
