import apiClient, { AUTH_LOGOUT_EVENT } from "@/api/client";
import type { LoginCredentials, RegisterData, User } from "@/types/auth";

export const register = async (data: RegisterData): Promise<User> => {
  const response = await apiClient.post<User>("/auth/register", data);
  return response.data;
};

export const login = async (credentials: LoginCredentials): Promise<void> => {
  await apiClient.post("/auth/login", credentials);
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
};

export const logout = async (): Promise<void> => {
  try {
    await apiClient.post("/auth/logout");
  } finally {
    window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
  }
};

export const requestPasswordReset = async (
  email: string,
): Promise<{ message: string }> => {
  const response = await apiClient.post<{ message: string }>(
    "/auth/password-reset/request",
    { email },
  );
  return response.data;
};

export const confirmPasswordReset = async (payload: {
  token: string;
  new_password: string;
}): Promise<void> => {
  await apiClient.post("/auth/password-reset/confirm", payload);
};
