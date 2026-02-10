import axios, { AxiosError } from "axios";

export const ACCESS_TOKEN_KEY = "access_token";
export const AUTH_LOGOUT_EVENT = "auth:logout";

const PUBLIC_AUTH_ENDPOINTS = ["/auth/login", "/auth/register"];

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);

  if (token) {
    config.headers = config.headers ?? {};
    (config.headers as Record<string, string>).Authorization =
      `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      const requestUrl = error.config?.url ?? "";
      const isPublicAuthEndpoint = PUBLIC_AUTH_ENDPOINTS.some((endpoint) =>
        requestUrl.includes(endpoint),
      );

      if (!isPublicAuthEndpoint) {
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));

        if (window.location.pathname !== "/login") {
          window.location.assign("/login");
        }
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
