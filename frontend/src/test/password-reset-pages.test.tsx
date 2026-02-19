import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "@/pages/auth/ForgotPasswordPage";
import LoginPage from "@/pages/auth/LoginPage";
import ResetPasswordPage from "@/pages/auth/ResetPasswordPage";

const mockRequestPasswordReset = vi.fn();
const mockConfirmPasswordReset = vi.fn();
const mockUseAuth = vi.fn();

vi.mock("@/api/auth", () => ({
  requestPasswordReset: (...args: unknown[]) => mockRequestPasswordReset(...args),
  confirmPasswordReset: (...args: unknown[]) => mockConfirmPasswordReset(...args),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("Password reset auth pages", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: null,
      loading: false,
      error: null,
      isAuthenticated: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      clearError: vi.fn(),
    });
  });

  it("shows forgot-password link on login page", () => {
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/forgot-password" element={<div>Forgot Password Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: "Forgot password?" }),
    ).toHaveAttribute("href", "/forgot-password");
  });

  it("submits forgot-password email and shows server message", async () => {
    mockRequestPasswordReset.mockResolvedValueOnce({
      message:
        "If an account exists for that email, password reset instructions will be sent.",
    });

    render(
      <MemoryRouter initialEntries={["/forgot-password"]}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "reset.user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));

    await waitFor(() => {
      expect(mockRequestPasswordReset).toHaveBeenCalledWith(
        "reset.user@example.com",
      );
    });
    expect(
      await screen.findByText(
        "If an account exists for that email, password reset instructions will be sent.",
      ),
    ).toBeInTheDocument();
  });

  it("shows cooldown message and disables submit when rate limited", async () => {
    mockRequestPasswordReset.mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed with status code 429",
      response: {
        status: 429,
        data: {
          detail:
            "Too many password reset requests. Please wait before requesting another reset email.",
        },
        headers: {
          "retry-after": "120",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/forgot-password"]}>
        <Routes>
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "reset.user@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Link" }));

    expect(
      await screen.findByText(
        "Too many password reset requests. Please wait before requesting another reset email.",
      ),
    ).toBeInTheDocument();
    const cooldownNotice = document.querySelector(".text-amber-800");
    expect(cooldownNotice).not.toBeNull();
    expect(cooldownNotice).toHaveTextContent(
      /Too many reset attempts\. Please try again in \d+s\./,
    );

    await waitFor(() => {
      const button = screen.getByRole("button");
      expect(button).toBeDisabled();
      expect(button).toHaveTextContent(/Try again in \d+s/);
    });
  });

  it("shows guidance when reset token is missing", () => {
    render(
      <MemoryRouter initialEntries={["/reset-password"]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Invalid Reset Link")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Request a new reset link" }),
    ).toHaveAttribute("href", "/forgot-password");
  });

  it("submits new password and redirects to login when token is valid", async () => {
    mockConfirmPasswordReset.mockResolvedValueOnce(undefined);

    render(
      <MemoryRouter initialEntries={["/reset-password?token=test-token"]}>
        <Routes>
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "ResetNewPass123!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "ResetNewPass123!" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Update Password" }));

    await waitFor(() => {
      expect(mockConfirmPasswordReset).toHaveBeenCalledWith({
        token: "test-token",
        new_password: "ResetNewPass123!",
      });
    });
    expect(await screen.findByText("Login Page")).toBeInTheDocument();
  });
});
