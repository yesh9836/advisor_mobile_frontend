import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getMyDeliverySettings } from "@/api/delivery-settings";
import Sidebar from "@/components/layout/Sidebar";

const mockUseAuth = vi.fn();
const getMyDeliverySettingsMock = vi.mocked(getMyDeliverySettings);

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/api/delivery-settings", () => ({
  getMyDeliverySettings: vi.fn(),
}));

const LocationProbe = () => {
  const location = useLocation();
  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
    </div>
  );
};

const renderSidebar = (
  route = "/dashboard",
  onClose: () => void = vi.fn(),
) => {
  render(
    <MemoryRouter initialEntries={[route]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <Sidebar isOpen={false} onClose={onClose} />
              <LocationProbe />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
};

describe("Sidebar role-based navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows advisor navigation for advisor users and displays CTA when both notifications are off", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
    });
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: false,
      sms_alerts_enabled: false,
      version: 1,
      updated_at: "2026-02-18T16:00:00Z",
      warnings: [],
    });

    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Buy Leads")).toBeInTheDocument();
    expect(screen.getByText("Lead Inbox")).toBeInTheDocument();
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Billing")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMyDeliverySettingsMock).toHaveBeenCalledTimes(1);
    });
    expect(screen.getByText("NEXT STEP")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Configure Notifications" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Lead Inventory")).not.toBeInTheDocument();
    expect(screen.queryByText("Orders")).not.toBeInTheDocument();
    expect(screen.queryByText("Imports")).not.toBeInTheDocument();
  });

  it("hides CTA when one notification channel is already enabled", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
    });
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: true,
      sms_alerts_enabled: false,
      version: 2,
      updated_at: "2026-02-18T16:10:00Z",
      warnings: [],
    });

    renderSidebar();

    await waitFor(() => {
      expect(getMyDeliverySettingsMock).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByText("NEXT STEP")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Configure Notifications" }),
    ).not.toBeInTheDocument();
  });

  it("redirects configure notifications to dashboard with settings query", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
    });
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: false,
      sms_alerts_enabled: false,
      version: 1,
      updated_at: "2026-02-18T16:20:00Z",
      warnings: [],
    });
    const onClose = vi.fn();

    renderSidebar("/leads", onClose);

    const configureButton = await screen.findByRole("button", {
      name: "Configure Notifications",
    });
    fireEvent.click(configureButton);

    expect(onClose).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/dashboard?openDeliverySettings=1",
      );
    });
  });

  it("hides CTA immediately when one notification channel is turned on", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
    });
    getMyDeliverySettingsMock.mockResolvedValue({
      email_alerts_enabled: false,
      sms_alerts_enabled: false,
      version: 1,
      updated_at: "2026-02-18T16:25:00Z",
      warnings: [],
    });

    renderSidebar();

    expect(
      await screen.findByRole("button", { name: "Configure Notifications" }),
    ).toBeInTheDocument();

    act(() => {
      window.dispatchEvent(
        new CustomEvent("delivery-settings-changed", {
          detail: {
            email_alerts_enabled: true,
            sms_alerts_enabled: false,
          },
        }),
      );
    });

    await waitFor(() => {
      expect(screen.queryByText("NEXT STEP")).not.toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Configure Notifications" }),
    ).not.toBeInTheDocument();
  });

  it("shows admin-only navigation for admin users", () => {
    mockUseAuth.mockReturnValue({
      user: { role: "admin" },
    });

    renderSidebar();

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Lead Inventory")).toBeInTheDocument();
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Orders")).toBeInTheDocument();
    expect(screen.getByText("Imports")).toBeInTheDocument();
    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("Plans")).toBeInTheDocument();
    expect(screen.getByText("First Purchase Offer")).toBeInTheDocument();
    expect(screen.getByText("License Reviews")).toBeInTheDocument();
    expect(screen.queryByText("Buy Leads")).not.toBeInTheDocument();
    expect(screen.queryByText("Lead Inbox")).not.toBeInTheDocument();
    expect(screen.queryByText("Billing")).not.toBeInTheDocument();
    expect(screen.queryByText("Profile")).not.toBeInTheDocument();
    expect(screen.queryByText("NEXT STEP")).not.toBeInTheDocument();
    expect(getMyDeliverySettingsMock).not.toHaveBeenCalled();
  });
});
