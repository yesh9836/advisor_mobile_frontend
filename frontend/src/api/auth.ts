import apiClient, { ACCESS_TOKEN_KEY, AUTH_LOGOUT_EVENT } from "@/api/client";
import type { LoginCredentials, RegisterData, Token, User } from "@/types/auth";

export const register = async (data: RegisterData): Promise<User> => {
  const response = await apiClient.post<User>("/auth/register", data);
  return response.data;
};

export const login = async (credentials: LoginCredentials): Promise<Token> => {
  const response = await apiClient.post<Token>("/auth/login", credentials);
  return response.data;
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>("/auth/me");
  return response.data;
};

export const logout = (): void => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));
};
