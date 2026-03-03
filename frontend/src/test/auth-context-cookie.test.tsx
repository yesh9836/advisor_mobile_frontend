import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import type { User } from "@/types/auth";
import { AUTH_ERROR_MESSAGES } from "@/utils/constants";

const mockLogin = vi.fn();
const mockLogout = vi.fn();
const mockRegister = vi.fn();
const mockGetCurrentUser = vi.fn();

vi.mock("@/api/auth", () => ({
  login: (...args: unknown[]) => mockLogin(...args),
  logout: (...args: unknown[]) => mockLogout(...args),
  register: (...args: unknown[]) => mockRegister(...args),
  getCurrentUser: (...args: unknown[]) => mockGetCurrentUser(...args),
}));

const authenticatedUser: User = {
  id: 1,
  email: "advisor.cookies@example.com",
  name: "Cookie Advisor",
  phone: "555-1212",
  role: "advisor",
  stripe_customer_id: null,
  created_at: "2026-01-01T00:00:00Z",
};

const ContextProbe = () => {
  const { user, loading, logout } = useAuth();

  return (
    <div>
      <div data-testid="loading-state">{loading ? "loading" : "ready"}</div>
      <div data-testid="user-email">{user?.email ?? "guest"}</div>
      <button type="button" onClick={() => void logout()}>
        Logout
      </button>
    </div>
  );
};

const AuthActionProbe = () => {
  const { loading, error, login, register } = useAuth();

  return (
    <div>
      <div data-testid="auth-loading">{loading ? "loading" : "ready"}</div>
      <div data-testid="auth-error">{error ?? "none"}</div>
      <button
        type="button"
        onClick={() => {
          void login({
            email: "advisor.cookies@example.com",
            password: "Secret123!",
          }).catch(() => undefined);
        }}
      >
        Trigger Login
      </button>
      <button
        type="button"
        onClick={() => {
          void register({
            name: "Cookie Advisor",
            email: "advisor.cookies@example.com",
            password: "Secret123!",
          }).catch(() => undefined);
        }}
      >
        Trigger Register
      </button>
    </div>
  );
};

describe("AuthContext cookie session behavior", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    mockLogout.mockReset();
    mockRegister.mockReset();
    mockGetCurrentUser.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("bootstraps session from /auth/me without localStorage token reads", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(authenticatedUser);
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem");

    render(
      <AuthProvider>
        <ContextProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading-state")).toHaveTextContent("ready");
      expect(screen.getByTestId("user-email")).toHaveTextContent(
        authenticatedUser.email,
      );
    });

    expect(mockGetCurrentUser).toHaveBeenCalledTimes(1);
    expect(getItemSpy).not.toHaveBeenCalledWith("access_token");
  });

  it("logout revokes server session and clears context user", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(authenticatedUser);
    mockLogout.mockResolvedValueOnce(undefined);

    render(
      <AuthProvider>
        <ContextProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent(
        authenticatedUser.email,
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("user-email")).toHaveTextContent("guest");
    });
  });

  it("clears context user even when logout request fails", async () => {
    mockGetCurrentUser.mockResolvedValueOnce(authenticatedUser);
    mockLogout.mockRejectedValueOnce(new Error("logout failed"));

    render(
      <AuthProvider>
        <ContextProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("user-email")).toHaveTextContent(
        authenticatedUser.email,
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Logout" }));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
      expect(screen.getByTestId("user-email")).toHaveTextContent("guest");
    });
  });

  it("uses login fallback copy when login throws non-api error", async () => {
    mockGetCurrentUser.mockRejectedValueOnce(new Error("Unauthenticated"));
    mockLogin.mockRejectedValueOnce("unexpected");

    render(
      <AuthProvider>
        <AuthActionProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    fireEvent.click(screen.getByRole("button", { name: "Trigger Login" }));

    await waitFor(() => {
      expect(screen.getByTestId("auth-error")).toHaveTextContent(
        AUTH_ERROR_MESSAGES.login,
      );
    });
  });

  it("uses register fallback copy when register throws non-api error", async () => {
    mockGetCurrentUser.mockRejectedValueOnce(new Error("Unauthenticated"));
    mockRegister.mockRejectedValueOnce("unexpected");

    render(
      <AuthProvider>
        <AuthActionProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    fireEvent.click(screen.getByRole("button", { name: "Trigger Register" }));

    await waitFor(() => {
      expect(screen.getByTestId("auth-error")).toHaveTextContent(
        AUTH_ERROR_MESSAGES.register,
      );
    });
  });

  it("does not authenticate when /auth/me contract validation fails", async () => {
    mockGetCurrentUser.mockRejectedValueOnce(
      new Error("Unexpected response format from /auth/me"),
    );

    render(
      <AuthProvider>
        <ContextProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading-state")).toHaveTextContent("ready");
      expect(screen.getByTestId("user-email")).toHaveTextContent("guest");
    });
  });

  it("prefers backend detail over login/register fallback copy", async () => {
    mockGetCurrentUser.mockRejectedValueOnce(new Error("Unauthenticated"));
    mockLogin.mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed with status code 401",
      response: { data: { detail: "Invalid credentials" } },
    });
    mockRegister.mockRejectedValueOnce({
      isAxiosError: true,
      message: "Request failed with status code 400",
      response: { data: { detail: "Email already registered" } },
    });

    render(
      <AuthProvider>
        <AuthActionProbe />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("auth-loading")).toHaveTextContent("ready");
    });

    fireEvent.click(screen.getByRole("button", { name: "Trigger Login" }));
    await waitFor(() => {
      expect(screen.getByTestId("auth-error")).toHaveTextContent(
        "Invalid credentials",
      );
    });

    fireEvent.click(screen.getByRole("button", { name: "Trigger Register" }));
    await waitFor(() => {
      expect(screen.getByTestId("auth-error")).toHaveTextContent(
        "Email already registered",
      );
    });
  });
});
