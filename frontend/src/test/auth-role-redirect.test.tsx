import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/pages/auth/LoginPage";
import RegisterPage from "@/pages/auth/RegisterPage";

const mockUseAuth = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

const baseAuth = {
  user: null,
  loading: false,
  error: null,
  isAuthenticated: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  clearError: vi.fn(),
};

const renderAuthRoute = (path: "/login" | "/register") => {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<div>Advisor Dashboard</div>} />
        <Route path="/admin" element={<div>Admin Dashboard</div>} />
      </Routes>
    </MemoryRouter>,
  );
};

describe("Auth pages role-based redirect", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects admin users from login to /admin", async () => {
    mockUseAuth.mockReturnValue({
      ...baseAuth,
      user: { role: "admin" },
      isAuthenticated: true,
    });

    renderAuthRoute("/login");

    expect(await screen.findByText("Admin Dashboard")).toBeInTheDocument();
  });

  it("redirects advisor users from login to /dashboard", async () => {
    mockUseAuth.mockReturnValue({
      ...baseAuth,
      user: { role: "advisor" },
      isAuthenticated: true,
    });

    renderAuthRoute("/login");

    expect(await screen.findByText("Advisor Dashboard")).toBeInTheDocument();
  });

  it("redirects admin users from register to /admin", async () => {
    mockUseAuth.mockReturnValue({
      ...baseAuth,
      user: { role: "admin" },
      isAuthenticated: true,
    });

    renderAuthRoute("/register");

    expect(await screen.findByText("Admin Dashboard")).toBeInTheDocument();
  });

  it("prefills register phone field with +1", () => {
    mockUseAuth.mockReturnValue(baseAuth);

    renderAuthRoute("/register");

    const phoneInput = screen.getByLabelText("Phone");
    expect(phoneInput).toHaveValue("+1");
  });

  it("normalizes register phone input to +1 digits only", async () => {
    mockUseAuth.mockReturnValue(baseAuth);

    renderAuthRoute("/register");

    const phoneInput = screen.getByLabelText("Phone");
    fireEvent.change(phoneInput, { target: { value: "+1 (305)-495-9490" } });

    await waitFor(() => {
      expect(phoneInput).toHaveValue("+13054959490");
    });
  });
});
