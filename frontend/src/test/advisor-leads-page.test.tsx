import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeadsPage from "@/pages/advisor/LeadsPage";

vi.mock("@/api/leads", () => ({
  downloadLeads: vi.fn(),
  getLeads: vi.fn(),
  saveLeadOutcome: vi.fn(),
}));

import { getLeads } from "@/api/leads";

const getLeadsMock = vi.mocked(getLeads);

const renderRoute = () => {
  render(
    <MemoryRouter initialEntries={["/leads"]}>
      <Routes>
        <Route path="/leads" element={<LeadsPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("Advisor LeadsPage server query state", () => {
  beforeEach(() => {
    getLeadsMock.mockReset();
    getLeadsMock.mockResolvedValue({
      items: [
        {
          id: 11,
          source: "manual_entry",
          state_code: "CA",
          zip_code: "94107",
          first_name: "Casey",
          last_name: "Advisor",
          mobile_phone: "555-111-2222",
          preferred_follow_up_method: null,
          best_time_to_reach: null,
          retirement_timeline: null,
          confidence_in_long_term_plan: null,
          most_important_retirement_activity: "Travel",
          planning_to_relocate_retirement: null,
          expected_retirement_income_source: null,
          overall_health: null,
          money_management_style: null,
          investor_profile_statement: null,
          investment_comfort_level: null,
          main_purpose_for_investing: null,
          retirement_savings_range: null,
          annual_household_income_range: null,
          total_investable_assets_range: "$250k-$500k",
          monthly_savings_range: null,
          wants_to_improve_strategy_timing: null,
          current_investment_strategies: null,
          has_financial_advisor: null,
          advisor_local_preference: null,
          owns_annuity: null,
          additional_notes: null,
          created_at: "2026-01-01T12:00:00Z",
          updated_at: null,
          outcome_status: null,
          outcome_notes: null,
          outcome_updated_at: null,
          is_downloaded: false,
          downloaded_at: null,
        },
      ],
      total: 51,
      page: 1,
      size: 25,
    });
  });

  it("fetches by filter/page state and resets page on filter changes", async () => {
    renderRoute();

    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(1, 25, {
        delivery_status: "all",
        outcome_status: "all",
      });
    });
    expect(await screen.findByText("Leads (51)")).toBeInTheDocument();
    expect(screen.queryByText("Email")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Call" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Text" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(2, 25, {
        delivery_status: "all",
        outcome_status: "all",
      });
    });

    fireEvent.change(screen.getByLabelText("Lead filter"), {
      target: { value: "Contacted" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(1, 25, {
        delivery_status: "all",
        outcome_status: "contacted",
      });
    });

    fireEvent.change(screen.getByLabelText("Delivery filter"), {
      target: { value: "Delivered" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(1, 25, {
        delivery_status: "delivered",
        outcome_status: "contacted",
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(2, 25, {
        delivery_status: "delivered",
        outcome_status: "contacted",
      });
    });

    fireEvent.change(screen.getByLabelText("Lead search"), {
      target: { value: "casey" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(1, 25, {
        delivery_status: "delivered",
        outcome_status: "contacted",
        search: "casey",
      });
    });
  });
});
