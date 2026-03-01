import axios, {
  AxiosError,
  AxiosHeaders,
  type InternalAxiosRequestConfig,
} from "axios";

import { APP_LOGIN_PATH, isAuthRoutePath } from "@/lib/app-path";

export const AUTH_LOGOUT_EVENT = "auth:logout";

const PUBLIC_AUTH_ENDPOINTS = [
  "/auth/login",
  "/auth/register",
  "/auth/password-reset/request",
  "/auth/password-reset/confirm",
];
const AUTH_SESSION_ENDPOINTS = ["/auth/refresh", "/auth/logout"];
const MUTATING_METHODS = new Set(["post", "put", "patch", "delete"]);
const REFRESH_TRANSIENT_FAILURE_COOLDOWN_MS = 3000;
const URL_PARSE_BASE =
  typeof window !== "undefined" ? window.location.origin : "http://localhost";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";
const CSRF_COOKIE_NAME = import.meta.env.VITE_AUTH_CSRF_COOKIE_NAME ?? "csrf_token";
const CSRF_HEADER_NAME = import.meta.env.VITE_AUTH_CSRF_HEADER_NAME ?? "X-CSRF-Token";

type RetryableRequestConfig = InternalAxiosRequestConfig & {
  _retry?: boolean;
};

const isMutatingMethod = (method?: string): boolean =>
  MUTATING_METHODS.has((method ?? "get").toLowerCase());

const normalizePathname = (pathname: string): string => {
  const normalized = pathname.replace(/\/+$/, "");
  return normalized || "/";
};

const getApiBasePath = (): string => {
  try {
    return normalizePathname(new URL(API_BASE_URL, URL_PARSE_BASE).pathname);
  } catch {
    return "/";
  }
};

const API_BASE_PATH = getApiBasePath();

const toNormalizedRequestPath = (requestUrl: string): string => {
  try {
    const normalizedPath = normalizePathname(new URL(requestUrl, URL_PARSE_BASE).pathname);
    if (API_BASE_PATH !== "/" && normalizedPath === API_BASE_PATH) {
      return "/";
    }
    if (API_BASE_PATH !== "/" && normalizedPath.startsWith(`${API_BASE_PATH}/`)) {
      return normalizePathname(normalizedPath.slice(API_BASE_PATH.length));
    }
    return normalizedPath;
  } catch {
    const pathOnly = requestUrl.split(/[?#]/, 1)[0] ?? "";
    return normalizePathname(pathOnly);
  }
};

const pathMatchesAny = (path: string, paths: string[]): boolean =>
  paths.some((knownPath) => knownPath === path);

export const classifyAuthEndpoint = (requestUrl: string): "public" | "session" | "other" => {
  const normalizedPath = toNormalizedRequestPath(requestUrl);
  if (pathMatchesAny(normalizedPath, PUBLIC_AUTH_ENDPOINTS)) {
    return "public";
  }
  if (pathMatchesAny(normalizedPath, AUTH_SESSION_ENDPOINTS)) {
    return "session";
  }
  return "other";
};

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

  if (!isAuthRoutePath(window.location.pathname)) {
    window.location.assign(APP_LOGIN_PATH);
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
let lastTransientRefreshFailureAt = 0;

const refreshSession = async (): Promise<void> => {
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  const headers = csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined;
  await refreshClient.post("/auth/refresh", undefined, { headers });
};

export const isTerminalRefreshFailure = (error: unknown): boolean => {
  if (!axios.isAxiosError(error)) {
    return false;
  }
  const statusCode = error.response?.status;
  return statusCode === 401 || statusCode === 403;
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

    const endpointType = classifyAuthEndpoint(requestUrl);

    if (endpointType === "public") {
      return Promise.reject(error);
    }

    if (endpointType === "session" || originalRequest._retry) {
      dispatchForcedLogout();
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      const now = Date.now();
      if (now - lastTransientRefreshFailureAt < REFRESH_TRANSIENT_FAILURE_COOLDOWN_MS) {
        return Promise.reject(error);
      }

      if (!refreshPromise) {
        refreshPromise = refreshSession().finally(() => {
          refreshPromise = null;
        });
      }

      await refreshPromise;
      lastTransientRefreshFailureAt = 0;
      return apiClient(originalRequest);
    } catch (refreshError) {
      if (isTerminalRefreshFailure(refreshError)) {
        dispatchForcedLogout();
      } else {
        lastTransientRefreshFailureAt = Date.now();
      }
      return Promise.reject(refreshError);
    }
  },
);

export default apiClient;
