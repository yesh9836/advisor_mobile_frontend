import { render, screen } from "@testing-library/react";
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

  it("renders all analytics charts on success", async () => {
    getAnalyticsOverview.mockResolvedValue({
      monthly_revenue: [
        { month: "2026-01", revenue_cents: 120000 },
        { month: "2026-02", revenue_cents: 90000 },
      ],
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
    });

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
    getAnalyticsOverview.mockResolvedValue({
      monthly_revenue: [],
      plan_breakdown: [],
      state_distribution: [],
      user_growth: [],
    });

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
});
