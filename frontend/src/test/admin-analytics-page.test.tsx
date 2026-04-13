import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "@/pages/admin/AnalyticsPage";

const getAnalyticsOverview = vi.fn();

vi.mock("@/api/admin", () => ({
  getAnalyticsOverview: (...args: unknown[]) => getAnalyticsOverview(...args),
}));

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const buildAnalyticsOverview = (overrides: Record<string, unknown> = {}) => ({
    monthly_revenue: [],
    monthly_revenue_total_months: 0,
    plan_breakdown: [],
    state_distribution: [],
    user_growth: [],
    user_growth_total_months: 0,
    user_growth_page: 1,
    user_growth_size: 6,
    user_growth_total_pages: 1,
    ...overrides,
  });

  it("renders all analytics charts on success", async () => {
    getAnalyticsOverview.mockResolvedValue(buildAnalyticsOverview({
      monthly_revenue: [
        { month: "2026-01", revenue_cents: 120000 },
        { month: "2026-02", revenue_cents: 90000 },
      ],
      monthly_revenue_total_months: 2,
      plan_breakdown: [
        {
          package_name: "Starter",
          purchases: 4,
          credits_granted: 40,
          credits_remaining: 10,
          revenue_cents: 40000,
        },
      ],
      state_distribution: [
        { state_code: "CA", lead_count: 12 },
        { state_code: "TX", lead_count: 8 },
      ],
      user_growth: [
        { month: "2026-01", new_users: 3 },
        { month: "2026-02", new_users: 5 },
      ],
      user_growth_total_months: 2,
    }));

    render(<AnalyticsPage />);

    expect(await screen.findByText("Monthly Revenue")).toBeInTheDocument();
    expect(screen.getByLabelText("Monthly revenue trend chart")).toBeInTheDocument();
    expect(screen.getByLabelText("Plan breakdown chart")).toBeInTheDocument();
    expect(screen.getByLabelText("Lead state distribution chart")).toBeInTheDocument();
    expect(screen.getByLabelText("Advisor user growth chart")).toBeInTheDocument();
  });

  it("shows loading state", async () => {
    getAnalyticsOverview.mockImplementation(() => new Promise(() => {}));

    render(<AnalyticsPage />);

    expect(screen.getByText("Loading analytics...")).toBeInTheDocument();
  });

  it("shows empty states when all datasets are empty", async () => {
    getAnalyticsOverview.mockResolvedValue(buildAnalyticsOverview());

    render(<AnalyticsPage />);

    expect(await screen.findByText("No monthly revenue data yet.")).toBeInTheDocument();
    expect(screen.getByText("No package breakdown data yet.")).toBeInTheDocument();
    expect(screen.getByText("No lead state distribution data yet.")).toBeInTheDocument();
    expect(screen.getByText("No advisor growth data yet.")).toBeInTheDocument();
  });

  it("shows API error state", async () => {
    getAnalyticsOverview.mockRejectedValue(new Error("analytics failed"));

    render(<AnalyticsPage />);

    expect(await screen.findByText("analytics failed")).toBeInTheDocument();
  });

  it("shows only the latest 12 months of monthly revenue", async () => {
    getAnalyticsOverview.mockResolvedValue(buildAnalyticsOverview({
      monthly_revenue: [
        { month: "2025-03", revenue_cents: 30000 },
        { month: "2025-04", revenue_cents: 40000 },
        { month: "2025-05", revenue_cents: 50000 },
        { month: "2025-06", revenue_cents: 60000 },
        { month: "2025-07", revenue_cents: 70000 },
        { month: "2025-08", revenue_cents: 80000 },
        { month: "2025-09", revenue_cents: 90000 },
        { month: "2025-10", revenue_cents: 100000 },
        { month: "2025-11", revenue_cents: 110000 },
        { month: "2025-12", revenue_cents: 120000 },
        { month: "2026-01", revenue_cents: 130000 },
        { month: "2026-02", revenue_cents: 140000 },
      ],
      monthly_revenue_total_months: 14,
    }));

    render(<AnalyticsPage />);

    expect(await screen.findByText("Showing latest 12 of 14 months.")).toBeInTheDocument();
    expect(screen.queryByText("Jan 2025: $100.00")).not.toBeInTheDocument();
    expect(screen.queryByText("Feb 2025: $200.00")).not.toBeInTheDocument();
    expect(screen.getByText("Mar 2025: $300.00")).toBeInTheDocument();
    expect(screen.getByText("Feb 2026: $1,400.00")).toBeInTheDocument();
  });

  it("pages user growth via the bounded backend contract", async () => {
    getAnalyticsOverview.mockImplementation((options?: { userGrowthPage?: number }) => {
      if (options?.userGrowthPage === 2) {
        return Promise.resolve(
          buildAnalyticsOverview({
            user_growth: [
              { month: "2025-01", new_users: 1 },
              { month: "2025-02", new_users: 2 },
            ],
            user_growth_total_months: 8,
            user_growth_page: 2,
            user_growth_size: 6,
            user_growth_total_pages: 2,
          }),
        );
      }

      return Promise.resolve(
        buildAnalyticsOverview({
          user_growth: [
            { month: "2025-03", new_users: 3 },
            { month: "2025-04", new_users: 4 },
            { month: "2025-05", new_users: 5 },
            { month: "2025-06", new_users: 6 },
            { month: "2025-07", new_users: 7 },
            { month: "2025-08", new_users: 8 },
          ],
          user_growth_total_months: 8,
          user_growth_page: 1,
          user_growth_size: 6,
          user_growth_total_pages: 2,
        }),
      );
    });

    render(<AnalyticsPage />);

    expect(
      await screen.findByText("Showing Mar 2025 - Aug 2025 • Page 1 of 2 • 8 total months"),
    ).toBeInTheDocument();
    expect(screen.getByText("Mar 2025")).toBeInTheDocument();
    expect(screen.getByText("Aug 2025")).toBeInTheDocument();
    expect(screen.queryByText("Jan 2025")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    expect(
      await screen.findByText("Showing Jan 2025 - Feb 2025 • Page 2 of 2 • 8 total months"),
    ).toBeInTheDocument();
    expect(screen.getByText("Jan 2025")).toBeInTheDocument();
    expect(screen.getByText("Feb 2025")).toBeInTheDocument();
    expect(screen.queryByText("Aug 2025")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));

    expect(
      await screen.findByText("Showing Mar 2025 - Aug 2025 • Page 1 of 2 • 8 total months"),
    ).toBeInTheDocument();
    expect(getAnalyticsOverview).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        monthlyRevenueLimit: 12,
        userGrowthPage: 1,
        userGrowthSize: 6,
      }),
    );
    expect(getAnalyticsOverview).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        monthlyRevenueLimit: 12,
        userGrowthPage: 2,
        userGrowthSize: 6,
      }),
    );
  });
});
