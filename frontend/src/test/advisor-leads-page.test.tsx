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
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((res) => {
      resolve = res;
    });
    return { promise, resolve };
  };

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
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        1,
        25,
        {
          delivery_status: "all",
          outcome_status: "all",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
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
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        2,
        25,
        {
          delivery_status: "all",
          outcome_status: "all",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });

    fireEvent.change(screen.getByLabelText("Lead filter"), {
      target: { value: "Contacted" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        1,
        25,
        {
          delivery_status: "all",
          outcome_status: "contacted",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });

    fireEvent.change(screen.getByLabelText("Delivery filter"), {
      target: { value: "Delivered" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        1,
        25,
        {
          delivery_status: "delivered",
          outcome_status: "contacted",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        2,
        25,
        {
          delivery_status: "delivered",
          outcome_status: "contacted",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });

    fireEvent.change(screen.getByLabelText("Lead search"), {
      target: { value: "casey" },
    });
    await waitFor(() => {
      expect(getLeadsMock).toHaveBeenLastCalledWith(
        1,
        25,
        {
          delivery_status: "delivered",
          outcome_status: "contacted",
          search: "casey",
        },
        expect.objectContaining({
          signal: expect.any(AbortSignal),
        }),
      );
    });
  });

  it("hides contact details for locked available leads", async () => {
    renderRoute();

    expect((await screen.findAllByText("Locked Lead")).length).toBeGreaterThan(
      0,
    );
    expect(screen.queryByText("Casey Advisor")).not.toBeInTheDocument();
    expect(
      screen.getAllByText("Unlock after delivery").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText("Contact details are available after delivery."),
    ).toBeInTheDocument();
  });

  it("ignores stale inbox responses after a newer filter request", async () => {
    const firstResponse = deferred<Awaited<ReturnType<typeof getLeads>>>();

    getLeadsMock
      .mockImplementationOnce(() => firstResponse.promise)
      .mockResolvedValueOnce({
        items: [
          {
            id: 24,
            source: "manual_entry",
            state_code: "TX",
            zip_code: "73301",
            first_name: "Taylor",
            last_name: "Fresh",
            mobile_phone: "555-111-3333",
            preferred_follow_up_method: null,
            best_time_to_reach: null,
            retirement_timeline: null,
            confidence_in_long_term_plan: null,
            most_important_retirement_activity: "Golf",
            planning_to_relocate_retirement: null,
            expected_retirement_income_source: null,
            overall_health: null,
            money_management_style: null,
            investor_profile_statement: null,
            investment_comfort_level: null,
            main_purpose_for_investing: null,
            retirement_savings_range: null,
            annual_household_income_range: null,
            total_investable_assets_range: "$500k-$1m",
            monthly_savings_range: null,
            wants_to_improve_strategy_timing: null,
            current_investment_strategies: null,
            has_financial_advisor: null,
            advisor_local_preference: null,
            owns_annuity: null,
            additional_notes: null,
            created_at: "2026-01-02T12:00:00Z",
            updated_at: null,
            outcome_status: "contacted",
            outcome_notes: null,
            outcome_updated_at: null,
            is_downloaded: true,
            downloaded_at: "2026-01-02T12:30:00Z",
          },
        ],
        total: 1,
        page: 1,
        size: 25,
      });

    renderRoute();

    fireEvent.change(screen.getByLabelText("Delivery filter"), {
      target: { value: "Delivered" },
    });

    expect((await screen.findAllByText("Taylor Fresh")).length).toBeGreaterThan(0);

    firstResponse.resolve({
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

    await waitFor(() => {
      expect(screen.queryAllByText("Casey Advisor")).toHaveLength(0);
    });
    expect(screen.queryAllByText("Taylor Fresh").length).toBeGreaterThan(0);
  });
});
