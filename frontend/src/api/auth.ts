import apiClient, { AUTH_LOGOUT_EVENT } from "@/api/client";
import { parseApiContract } from "@/api/contract";
import type { LoginCredentials, RegisterData, User } from "@/types/auth";
import { z } from "zod";

const userSchema: z.ZodType<User> = z
  .object({
    id: z.number(),
    email: z.string(),
    name: z.string(),
    phone: z.string().nullable(),
    role: z.string(),
    stripe_customer_id: z.string().nullable(),
    created_at: z.string(),
  })
  .passthrough();

const passwordResetResponseSchema = z
  .object({
    message: z.string(),
  })
  .passthrough();

export const register = async (data: RegisterData): Promise<User> => {
  const response = await apiClient.post<User>("/auth/register", data);
  return parseApiContract(userSchema, response.data, "/auth/register");
};

export const login = async (credentials: LoginCredentials): Promise<void> => {
  await apiClient.post("/auth/login", credentials);
};

export const getCurrentUser = async (): Promise<User> => {
  const response = await apiClient.get<User>("/auth/me");
  return parseApiContract(userSchema, response.data, "/auth/me");
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
  return parseApiContract(
    passwordResetResponseSchema,
    response.data,
    "/auth/password-reset/request",
  );
};

export const confirmPasswordReset = async (payload: {
  token: string;
  new_password: string;
}): Promise<void> => {
  await apiClient.post("/auth/password-reset/confirm", payload);
};
