import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProtectedRoute from "@/components/auth/ProtectedRoute";

const mockUseAuth = vi.fn();

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("ProtectedRoute role mismatch redirects", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects admin user away from advisor-only routes to /admin", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "admin" },
      loading: false,
    });

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute allowedRoles={["advisor"]}>
                <div>Advisor Dashboard</div>
              </ProtectedRoute>
            }
          />
          <Route path="/admin" element={<div>Admin Home</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Admin Home")).toBeInTheDocument();
  });

  it("redirects advisor user away from admin-only routes to /dashboard", async () => {
    mockUseAuth.mockReturnValue({
      user: { role: "advisor" },
      loading: false,
    });

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={["admin"]}>
                <div>Admin Dashboard</div>
              </ProtectedRoute>
            }
          />
          <Route path="/dashboard" element={<div>Advisor Home</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByText("Advisor Home")).toBeInTheDocument();
  });
});
