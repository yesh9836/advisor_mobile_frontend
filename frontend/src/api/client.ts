import axios, {
  AxiosError,
  AxiosHeaders,
  type InternalAxiosRequestConfig,
} from "axios";

export const AUTH_LOGOUT_EVENT = "auth:logout";

const PUBLIC_AUTH_ENDPOINTS = ["/auth/login", "/auth/register"];
const AUTH_SESSION_ENDPOINTS = ["/auth/refresh", "/auth/logout"];
const MUTATING_METHODS = new Set(["post", "put", "patch", "delete"]);

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const CSRF_COOKIE_NAME = import.meta.env.VITE_AUTH_CSRF_COOKIE_NAME ?? "csrf_token";
const CSRF_HEADER_NAME = import.meta.env.VITE_AUTH_CSRF_HEADER_NAME ?? "X-CSRF-Token";

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

const isMutatingMethod = (method?: string): boolean =>
  MUTATING_METHODS.has((method ?? "get").toLowerCase());

const urlMatchesAny = (url: string, paths: string[]): boolean =>
  paths.some((path) => url.includes(path));

const readCookie = (cookieName: string): string | null => {
  const cookies = document.cookie ? document.cookie.split("; ") : [];

  for (const cookie of cookies) {
    const [name, ...valueParts] = cookie.split("=");
    if (name === cookieName) {
      return decodeURIComponent(valueParts.join("="));
    }
  }

  return null;
};

const setHeader = (
  headers: InternalAxiosRequestConfig["headers"],
  name: string,
  value: string,
): InternalAxiosRequestConfig["headers"] => {
  const normalizedHeaders =
    headers instanceof AxiosHeaders ? headers : new AxiosHeaders(headers);
  normalizedHeaders.set(name, value);
  return normalizedHeaders;
};

const withCsrfHeader = (
  config: InternalAxiosRequestConfig,
  csrfToken: string | null,
): InternalAxiosRequestConfig => {
  if (!csrfToken || !isMutatingMethod(config.method)) {
    return config;
  }

  config.headers = setHeader(config.headers, CSRF_HEADER_NAME, csrfToken);
  return config;
};

const dispatchForcedLogout = () => {
  window.dispatchEvent(new Event(AUTH_LOGOUT_EVENT));

  if (window.location.pathname !== "/login" && window.location.pathname !== "/register") {
    window.location.assign("/login");
  }
};

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshPromise: Promise<void> | null = null;

const refreshSession = async (): Promise<void> => {
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  const headers = csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined;
  await refreshClient.post("/auth/refresh", undefined, { headers });
};

apiClient.interceptors.request.use((config) => {
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  return withCsrfHeader(config, csrfToken);
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;
    const statusCode = error.response?.status;
    const requestUrl = originalRequest?.url ?? "";

    if (!originalRequest || statusCode !== 401) {
      return Promise.reject(error);
    }

    if (urlMatchesAny(requestUrl, PUBLIC_AUTH_ENDPOINTS)) {
      return Promise.reject(error);
    }

    if (urlMatchesAny(requestUrl, AUTH_SESSION_ENDPOINTS) || originalRequest._retry) {
      dispatchForcedLogout();
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = refreshSession().finally(() => {
          refreshPromise = null;
        });
      }

      await refreshPromise;
      return apiClient(originalRequest);
    } catch (refreshError) {
      dispatchForcedLogout();
      return Promise.reject(refreshError);
    }
  },
);

export default apiClient;
