import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/pages/advisor/DashboardPage";

vi.mock("@/api/leads", () => ({
  getLeadDashboardSummary: vi.fn(),
  getLeads: vi.fn(),
}));

vi.mock("@/api/delivery-settings", () => ({
  getMyDeliverySettings: vi.fn(),
  updateMyDeliverySettings: vi.fn(),
}));

import {
  getLeadDashboardSummary,
  getLeads,
} from "@/api/leads";
import {
  getMyDeliverySettings,
  updateMyDeliverySettings,
} from "@/api/delivery-settings";

const getLeadDashboardSummaryMock = vi.mocked(getLeadDashboardSummary);
const getLeadsMock = vi.mocked(getLeads);
const getMyDeliverySettingsMock = vi.mocked(getMyDeliverySettings);
const updateMyDeliverySettingsMock = vi.mocked(updateMyDeliverySettings);

const summaryWithSettings = (emailEnabled: boolean, smsEnabled: boolean) => ({
  leads_delivered_7_days: 0,
  appointments_set_7_days: 0,
  cost_per_appointment: 0,
  currency: "USD",
  settings: {
    email_alerts_enabled: emailEnabled,
    sms_alerts_enabled: smsEnabled,
    target_states: [],
    min_assets: null,
    daily_download_limit: null,
  },
});

const renderRoute = () => {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("Advisor Dashboard delivery settings editor", () => {
  beforeEach(() => {
    getLeadDashboardSummaryMock.mockReset();
    getLeadsMock.mockReset();
    getMyDeliverySettingsMock.mockReset();
    updateMyDeliverySettingsMock.mockReset();

    getLeadsMock.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      size: 3,
    });
  });

  it("applies toggle changes instantly and refreshes summary snapshot", async () => {
    getLeadDashboardSummaryMock
      .mockResolvedValueOnce(summaryWithSettings(false, false))
      .mockResolvedValueOnce(summaryWithSettings(true, false));
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: false,
      sms_alerts_enabled: false,
      version: 1,
      updated_at: "2026-02-17T14:00:00Z",
      warnings: [],
    });
    updateMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: true,
      sms_alerts_enabled: false,
      version: 2,
      updated_at: "2026-02-17T14:01:00Z",
      warnings: [],
    });

    renderRoute();

    await waitFor(() => {
      expect(getLeadDashboardSummaryMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Edit Settings" }));
    const emailToggle = await screen.findByLabelText("Email alerts");
    expect(emailToggle).not.toBeChecked();

    fireEvent.click(emailToggle);

    await waitFor(() => {
      expect(updateMyDeliverySettingsMock).toHaveBeenCalledWith({
        email_alerts_enabled: true,
        expected_version: 1,
      });
    });
    await waitFor(() => {
      expect(getLeadDashboardSummaryMock).toHaveBeenCalledTimes(2);
    });

    expect(screen.getByTestId("delivery-email-status")).toHaveTextContent("On");
    expect(screen.getByText("Email alerts enabled.")).toBeInTheDocument();
  });

  it("rolls back toggle state when update fails", async () => {
    getLeadDashboardSummaryMock.mockResolvedValue(summaryWithSettings(false, false));
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: false,
      sms_alerts_enabled: false,
      version: 1,
      updated_at: "2026-02-17T14:00:00Z",
      warnings: [],
    });
    updateMyDeliverySettingsMock.mockRejectedValue(new Error("Update failed"));

    renderRoute();

    await waitFor(() => {
      expect(getLeadDashboardSummaryMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole("button", { name: "Edit Settings" }));
    const emailToggle = await screen.findByLabelText("Email alerts");
    expect(emailToggle).not.toBeChecked();

    fireEvent.click(emailToggle);
    expect(emailToggle).toBeChecked();

    await waitFor(() => {
      expect(updateMyDeliverySettingsMock).toHaveBeenCalledWith({
        email_alerts_enabled: true,
        expected_version: 1,
      });
    });

    await waitFor(() => {
      expect(emailToggle).not.toBeChecked();
    });
    expect(screen.getByText("Update failed")).toBeInTheDocument();
    expect(screen.getByTestId("delivery-email-status")).toHaveTextContent("Off");
    expect(getLeadDashboardSummaryMock).toHaveBeenCalledTimes(1);
  });
});
